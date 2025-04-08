#!/usr/bin/env python3

"""
WISR Media Random Data Generator
Generates random sample data matching the WISR Media data model and uploads to Elasticsearch
This updated version includes support for:
- Multiple tenants
- Multiple properties per tenant
- Multiple devices per property
- Configurable number of media items per device
- Enhanced object detection with wildlife, people, and vehicles
- Enrichment process tracking
- Snake_case field names following Elasticsearch best practices

# Install dependencies
pip install elasticsearch pyyaml requests

# Generate and upload data with a configuration file
python wisr_generator.py --config example-config.yaml --endpoint https://your-elasticsearch-endpoint:9243 --api-key YOUR_API_KEY

# Just generate data without uploading
python wisr_generator.py --config example-config.yaml --output test_data.json

# Generate a specific number of records per device
python wisr_generator.py --config example-config.yaml --count 20 --output test_data.json

"""
import json
import random
import uuid
import argparse
import yaml
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
import math
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Default configuration
DEFAULT_CONFIG = {
    "tenants": [
        {
            "id": "tenant-001",
            "name": "Default Tenant",
            "properties": [
                {
                    "id": "prop-123456",
                    "name": "Rain Creek Ranch",
                    "timezone": "America/Chicago",
                    "devices": [
                        {
                            "id": "device-001",
                            "name": "Main Gate Camera",
                            "make": "Axis",
                            "model": "P1448-LE",
                            "serial_number": "ACCC8E123456",
                            "location": [-99.607781, 30.990075],
                            "boundary_id": "bound-001"
                        }
                    ]
                }
            ]
        }
    ],
    "media_count_per_device": 10,
    "date_range": {
        "days_back": 30
    },
    "detection": {
        "wildlife_probability": 0.6,
        "people_probability": 0.2,
        "vehicle_probability": 0.15,
        "empty_probability": 0.05
    },
    "elasticsearch": {
        "use_api_key": True,
        "verify_ssl": True,
        "index_prefix": "wisr-media"
    }
}

# Sample data constants
WILDLIFE_TYPES = [
    {
        "class": "deer",
        "subclass": "whitetail",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "cervidae", "odocoileus", "virginianus"
        ],
        "sex_options": ["buck", "doe"],
        "age_options": ["fawn", "yearling", "mature", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "bedding"],
        "identified_names": {
            "buck": ["Big Eight", "Wide Spread", "Tall Tines", "Drop Tine"],
            "doe": ["Big Mama", "Lead Doe", "Notch Ear", "Limpy"]
        },
        "color_options": ["brown", "tan", "gray-brown"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "deer",
        "subclass": "axis",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "cervidae", "axis", "axis"
        ],
        "sex_options": ["buck", "doe"],
        "age_options": ["fawn", "yearling", "mature", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "bedding"],
        "identified_names": {
            "buck": ["Spots", "Long Beam", "Triple Point", "Chocolate"],
            "doe": ["Speckles", "Beauty", "Alert One", "Watchful"]
        },
        "color_options": ["reddish-brown", "chestnut", "spotted-white"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "deer",
        "subclass": "red_stag",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "cervidae", "cervus", "elaphus"
        ],
        "sex_options": ["stag", "hind"],
        "age_options": ["calf", "yearling", "mature", "royal", "imperial"],
        "action_options": ["feeding", "walking", "running", "standing", "bugling"],
        "identified_names": {
            "stag": ["Royal", "Emperor", "Crown King", "Massive"],
            "hind": ["Matriarch", "Lead Hind", "Swift One"]
        },
        "color_options": ["reddish-brown", "dark-brown", "tan"],
        "size_options": ["large", "very-large"]
    },
    {
        "class": "deer",
        "subclass": "fallow",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "cervidae", "dama", "dama"
        ],
        "sex_options": ["buck", "doe"],
        "age_options": ["fawn", "yearling", "mature", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "bedding"],
        "identified_names": {
            "buck": ["Palms", "Wide One", "White Knight", "Dark Prince"],
            "doe": ["Dappled", "Light Foot", "Watcher"]
        },
        "color_options": ["spotted", "white", "dark-brown", "chestnut"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "blackbuck",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "antilope", "cervicapra"
        ],
        "sex_options": ["male", "female"],
        "age_options": ["juvenile", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "leaping"],
        "identified_names": {
            "male": ["Twisted Horn", "Black Prince", "Leaper", "Spiral"],
            "female": ["Tan Beauty", "Swift", "Alert One"]
        },
        "color_options": ["black-and-white", "tan", "brown"],
        "size_options": ["medium"]
    },
    {
        "class": "addax",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "addax", "nasomaculatus"
        ],
        "sex_options": ["male", "female"],
        "age_options": ["juvenile", "adult"],
        "action_options": ["feeding", "walking", "standing", "resting"],
        "identified_names": {
            "male": ["Desert King", "Spiral", "White Sheikh", "Long Horn"],
            "female": ["Sand Dancer", "Pale One", "Dune"]
        },
        "color_options": ["white", "sandy", "light-tan"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "aoudad",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "ammotragus", "lervia"
        ],
        "sex_options": ["ram", "ewe"],
        "age_options": ["lamb", "juvenile", "adult"],
        "action_options": ["climbing", "feeding", "walking", "standing", "resting"],
        "identified_names": {
            "ram": ["Mountain King", "Curl", "Rocky", "Old Man"],
            "ewe": ["Climber", "Watcher", "Nimble"]
        },
        "color_options": ["tan", "sandy", "reddish-brown"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "oryx",
        "subclass": "gemsbok",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "oryx", "gazella"
        ],
        "sex_options": ["male", "female"],
        "age_options": ["juvenile", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "grazing"],
        "identified_names": {
            "male": ["Spear", "Long Horn", "Warrior", "Painted Face"],
            "female": ["Elegant", "Desert Queen", "Sharp Point"]
        },
        "color_options": ["tan-and-black", "gray-and-black", "brown-and-white"],
        "size_options": ["large"]
    },
    {
        "class": "ibex",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "capra", "nubiana"
        ],
        "sex_options": ["billy", "nanny"],
        "age_options": ["kid", "juvenile", "adult"],
        "action_options": ["climbing", "feeding", "walking", "standing", "jumping"],
        "identified_names": {
            "billy": ["Ridge Walker", "Curved Horn", "Summit", "Old Climber"],
            "nanny": ["Rock Dancer", "Hill Watcher", "Agile One"]
        },
        "color_options": ["brown", "tan", "gray-brown"],
        "size_options": ["medium"]
    },
    {
        "class": "nilgai",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "bovidae", "boselaphus", "tragocamelus"
        ],
        "sex_options": ["bull", "cow"],
        "age_options": ["calf", "juvenile", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "grazing"],
        "identified_names": {
            "bull": ["Blue Bull", "White Throat", "Giant", "Massive"],
            "cow": ["Brown Beauty", "Swift Runner", "Watchful"]
        },
        "color_options": ["bluish-gray", "brown", "grayish-brown"],
        "size_options": ["large", "very-large"]
    },
    {
        "class": "sika",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "cervidae", "cervus", "nippon"
        ],
        "sex_options": ["stag", "hind"],
        "age_options": ["calf", "yearling", "adult"],
        "action_options": ["feeding", "walking", "running", "standing", "calling"],
        "identified_names": {
            "stag": ["Dappled King", "Whistler", "Forest Ghost", "Bamboo"],
            "hind": ["Spots", "Quiet Walker", "Silk"]
        },
        "color_options": ["chestnut", "spotted", "dark-brown"],
        "size_options": ["medium"]
    },
    {
        "class": "coyote",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "carnivora",
            "canidae", "canis", "latrans"
        ],
        "sex_options": [None, "male", "female"],
        "age_options": ["juvenile", "adult"],
        "action_options": ["walking", "running", "hunting", "carrying prey"],
        "identified_names": {
            "male": ["Alpha", "Scout", "Trickster"],
            "female": ["Alpha Female", "Hunter"]
        },
        "color_options": ["gray", "tan", "reddish-brown"],
        "size_options": ["medium"]
    },
    {
        "class": "boar",
        "subclass": "wild",
        "taxonomic": [
            "animalia", "chordata", "mammalia", "artiodactyla",
            "suidae", "sus", "scrofa"
        ],
        "sex_options": [None, "boar", "sow"],
        "age_options": ["piglet", "juvenile", "adult"],
        "action_options": ["foraging", "rooting", "walking", "wallowing"],
        "identified_names": {
            "boar": ["Big Tusker", "Razorback", "Old Scar"],
            "sow": ["Matriarch", "Lead Sow"]
        },
        "color_options": ["black", "brown", "dark-gray"],
        "size_options": ["medium", "large"]
    },
    {
        "class": "turkey",
        "subclass": "wild",
        "taxonomic": [
            "animalia", "chordata", "aves", "galliformes",
            "phasianidae", "meleagris", "gallopavo"
        ],
        "sex_options": ["tom", "hen", "jake"],
        "age_options": ["poult", "juvenile", "adult"],
        "action_options": ["feeding", "strutting", "walking", "dust bathing"],
        "identified_names": {
            "tom": ["Long Beard", "Double Spurs", "King Strut"],
            "hen": ["Lead Hen", "Nesting Mama"]
        },
        "color_options": ["brown", "dark", "iridescent"],
        "size_options": ["small", "medium"]
    },
    {
        "class": "bobcat",
        "subclass": None,
        "taxonomic": [
            "animalia", "chordata", "mammalia", "carnivora",
            "felidae", "lynx", "rufus"
        ],
        "sex_options": [None, "male", "female"],
        "age_options": ["juvenile", "adult"],
        "action_options": ["walking", "stalking", "running", "hunting"],
        "identified_names": {
            "male": ["Spots", "Ghost", "Shadow"],
            "female": ["Huntress", "Prowler"]
        },
        "color_options": ["tan", "spotted", "reddish-brown"],
        "size_options": ["small", "medium"]
    }
]

# New person detection options
PERSON_TYPES = {
    "category": "person",
    "class": ["adult", "child"],
    "subclass": ["hunter", "worker"],
    "gender_options": ["male", "female", None],
    "age_range_options": ["child", "teenager", "adult", "elderly"],
    "action_options": ["walking", "standing", "hunting", "working", "driving", "riding"],
    "clothing": {
        "upper_body": ["t-shirt", "jacket", "hoodie", "flannel", "camo", "vest", "coat"],
        "lower_body": ["jeans", "pants", "shorts", "camo pants"],
        "headwear": ["cap", "hat", "helmet", "beanie", None]
    },
    "color_options": ["blue", "green", "brown", "black", "red", "orange", "camo", "tan", "gray"],
    "posture_options": ["standing", "crouching", "sitting", "walking", "running"],
    "build_options": ["small", "medium", "large", "thin", "heavy"],
    "accessories_options": ["backpack", "binoculars", "rifle", "fishing gear", "camera", "phone", None],
    "carrying_options": ["bag", "tool", "weapon", "equipment", None]
}

# New vehicle detection options  
VEHICLE_TYPES = {
    "category": "vehicle",
    "class": "vehicle",
    "subclass": ["car", "truck", "atv", "suv", "motorcycle", "utility vehicle"],
    "make_options": ["Ford", "Chevrolet", "Toyota", "Polaris", "Honda", "Jeep", "Dodge", "Kawasaki", "John Deere"],
    "model_options": {
        "Ford": ["F-150", "Ranger", "Bronco", "Explorer"],
        "Chevrolet": ["Silverado", "Colorado", "Tahoe", "Suburban"],
        "Toyota": ["Tacoma", "Tundra", "4Runner", "Land Cruiser"],
        "Polaris": ["Ranger", "RZR", "Sportsman"],
        "Honda": ["Pioneer", "Foreman", "Rancher", "Talon"],
        "Jeep": ["Wrangler", "Gladiator", "Cherokee"],
        "Dodge": ["Ram 1500", "Ram 2500", "Durango"],
        "Kawasaki": ["Mule", "Teryx", "Brute Force"],
        "John Deere": ["Gator", "Tractor"]
    },
    "color_options": ["black", "white", "silver", "red", "blue", "green", "brown", "orange", "camo"],
    "year_range_options": ["2010-2015", "2015-2020", "2020-2025"],
    "action_options": ["moving", "parked", "idling"],
    "distinctive_marks_options": ["light bar", "winch", "roof rack", "lift kit", "mud tires", None],
    "wheels_options": [2, 4, 6],
    "doors_options": [2, 4, 5]
}

WEATHER_CONDITIONS = [
    {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"},
    {"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"},
    {"id": 802, "main": "Clouds", "description": "scattered clouds", "icon": "03d"},
    {"id": 803, "main": "Clouds", "description": "broken clouds", "icon": "04d"},
    {"id": 804, "main": "Clouds", "description": "overcast clouds", "icon": "04d"},
    {"id": 500, "main": "Rain", "description": "light rain", "icon": "10d"},
    {"id": 501, "main": "Rain", "description": "moderate rain", "icon": "10d"},
    {"id": 502, "main": "Rain", "description": "heavy intensity rain", "icon": "10d"}
]

MOON_PHASES = [
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent"
]

SUN_POSITIONS = ["dawn", "day", "dusk", "night"]
IMAGE_FORMATS = ["jpg", "png"]
VIDEO_FORMATS = ["mp4", "mov"]
MIME_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "mp4": "video/mp4",
    "mov": "video/quicktime"
}
RESOLUTIONS = {
    "720p": (1280, 720, 0.9216),
    "1080p": (1920, 1080, 2.0736),
    "4K": (3840, 2160, 8.2944)
}
VIDEO_CODECS = ["h264", "h265"]
TRIGGER_TYPES = ["motion", "scheduled", "manual"]
INGESTION_METHODS = ["email", "ftp", "manual", "api"]
ENRICHMENT_PROCESS_TYPES = ["weather", "astronomical", "object-detection", "video-processing", "license-plate-reading"]
ENRICHMENT_SERVICES = ["openweathermap", "skyfield", "wildlife-detector", "video-analyzer", "alpr-service"]
ENRICHMENT_STATUS = ["success", "failed", "partial", "skipped"]
ENRICHMENT_PRIORITIES = ["high", "medium", "low"]

class ElasticsearchUploader:
    """Class to handle uploading data to Elasticsearch"""
    
    def __init__(self, config):
        """Initialize uploader with Elasticsearch connection details"""
        self.config = config
        self.es_config = config["elasticsearch"]
        self.index_prefix = self.es_config["index_prefix"]
        
        # Determine authentication method
        if self.es_config.get("use_api_key", True):
            # Use API key
            self.client = Elasticsearch(
                self.es_config["endpoint"],
                api_key=self.es_config["api_key"],
                verify_certs=self.es_config.get("verify_ssl", True)
            )
        else:
            # Use username/password
            self.client = Elasticsearch(
                self.es_config["endpoint"],
                basic_auth=(self.es_config["username"], self.es_config["password"]),
                verify_certs=self.es_config.get("verify_ssl", True)
            )
    
    def check_connection(self):
        """Check if we can connect to Elasticsearch"""
        try:
            info = self.client.info()
            return True, info
        except Exception as e:
            return False, str(e)
    
    def get_index_name(self, tenant_id):
        """Get index name for a tenant"""
        return f"{self.index_prefix}-{tenant_id.replace('-', '')}"
    
    def upload_records(self, records, batch_size=100, refresh=True):
        """Upload records to Elasticsearch using the bulk API"""
        total_records = len(records)
        
        # Group records by tenant
        tenant_records = {}
        for record in records:
            tenant_id = record["tenant_id"]
            if tenant_id not in tenant_records:
                tenant_records[tenant_id] = []
            tenant_records[tenant_id].append(record)
        
        successful = 0
        errors = []
        
        for tenant_id, tenant_batch in tenant_records.items():
            index_name = self.get_index_name(tenant_id)
                        
            # Split into batches
            tenant_batches = [tenant_batch[i:i+batch_size] for i in range(0, len(tenant_batch), batch_size)]
            
            print(f"Uploading {len(tenant_batch)} records to {index_name} in {len(tenant_batches)} batches...")
            
            # Process each batch
            for i, batch in enumerate(tenant_batches, 1):
                # print(f"Uploading batch {i}/{len(tenant_batches)} ({len(batch)} records)...")
                
                start_time = time.time()

                # Prepare bulk operation
                bulk_operations = [
                    { "_op_type": "create",
                      "_index": index_name,
                      "_source": record
                    }
                    for record in batch
                ]

                # Execute bulk operation
                try:
                    # Change stats_only to False to get detailed error responses
                    success, errors_response = bulk(
                        self.client,
                        bulk_operations,
                        refresh=refresh,
                        raise_on_error=False,
                        stats_only=False  # Set to False to get detailed errors
                    )

                    end_time = time.time()
                    duration = end_time - start_time
                    print(f"   Uploaed Batch {i}/{len(tenant_batches)} with {len(batch)} records in {duration:.2f} seconds")

                    successful += len([item for item in errors_response if "index" in item and not "error" in item["index"]])
                    
                    # Process and display detailed errors
                    failed_items = [item for item in errors_response if "index" in item and "error" in item["index"]]
                    if failed_items:
                        print(f" {len(failed_items)} operations failed in this batch")
                        
                        # Log detailed errors (first 5 for brevity)
                        for idx, item in enumerate(failed_items[:5]):
                            error_details = item["index"]["error"]
                            error_type = error_details.get("type", "unknown")
                            error_reason = error_details.get("reason", "unknown")
                            doc_id = item["index"].get("_id", "unknown")
                            
                            print(f"   Error {idx+1}: Document ID: {doc_id}")
                            print(f"     Type: {error_type}")
                            print(f"     Reason: {error_reason}")
                            
                            # If there's a causedBy field, show that too
                            if "caused_by" in error_details:
                                print(f"     Caused by: {error_details['caused_by'].get('reason', 'unknown')}")
                        
                        if len(failed_items) > 5:
                            print(f"   ... and {len(failed_items) - 5} more errors")
                            
                        errors.append({
                            "batch": i, 
                            "failed": len(failed_items),
                            "sample_errors": [
                                {
                                    "id": item["index"].get("_id", "unknown"),
                                    "type": item["index"]["error"].get("type", "unknown"),
                                    "reason": item["index"]["error"].get("reason", "unknown")
                                } 
                                for item in failed_items[:5]
                            ]
                        })
                except Exception as e:
                    print(f" Error uploading batch: {str(e)}")
                    errors.append({"batch": i, "error": str(e)})       

        return successful, errors

class MediaGenerator:
    def __init__(self, config):
        """Initialize the generator with configuration"""
        self.config = config
        
        # Calculate date range
        self.end_date = datetime.now(timezone.utc)
        days_back = config.get("date_range", {}).get("days_back", 30)
        self.start_date = self.end_date - timedelta(days=days_back)
        
        # Detection probabilities
        self.detection_config = config.get("detection", {})
        self.wildlife_probability = self.detection_config.get("wildlife_probability", 0.85)
        self.people_probability = self.detection_config.get("people_probability", 0.04)
        self.vehicle_probability = self.detection_config.get("vehicle_probability", 0.06)
        self.empty_probability = self.detection_config.get("empty_probability", 0.05)
        
        # Normalize probabilities
        total_prob = (self.wildlife_probability + self.people_probability + 
                     self.vehicle_probability + self.empty_probability)
        if total_prob != 1.0:
            self.wildlife_probability /= total_prob
            self.people_probability /= total_prob
            self.vehicle_probability /= total_prob
            self.empty_probability /= total_prob
    
    def generate_random_date(self):
        """Generate a random date within the date range"""
        time_diff = self.end_date - self.start_date
        random_seconds = random.randint(0, int(time_diff.total_seconds()))
        return self.start_date + timedelta(seconds=random_seconds)
    
    def add_timestamp_jitter(self, base_time, max_seconds=60):
        """Add a small random time difference"""
        jitter_seconds = random.randint(0, max_seconds)
        return base_time + timedelta(seconds=jitter_seconds)
    
    def generate_filename(self, capture_date, index):
        """Generate a filename based on date and index"""
        formatted_date = capture_date.strftime("%Y%m%d%H%M%S000")
        return f"{index:02d}_{formatted_date}.jpg"
    
    def get_sun_position(self, hour):
        """Determine sun position based on hour of day"""
        if 6 <= hour < 7:
            return "dawn"
        elif 7 <= hour < 19:
            return "day"
        elif 19 <= hour < 20:
            return "dusk"
        else:
            return "night"
    
    def generate_random_location(self, base_lon, base_lat, max_offset=0.002):
        """Generate a random location near the base coordinates"""
        lat_offset = random.uniform(-max_offset, max_offset)
        lon_offset = random.uniform(-max_offset, max_offset)
        # Return in [lon, lat] format for geo_point compatibility
        return [base_lon + lon_offset, base_lat + lat_offset]
    
    def generate_storage_paths(self, tenant_id, property_id, device_id, capture_date, media_id, format):
        """Generate storage paths for the media"""
        date_path = capture_date.strftime("%Y/%m/%d")
        base_path = f"{tenant_id}/{property_id}/{device_id}/{date_path}"
        return {
            "original": f"{base_path}/{media_id}.{format}",
            "thumbnail": f"{base_path}/thumbnails/{media_id}.jpg",
            "medium": f"{base_path}/medium/{media_id}.{format}",
            "processed": f"{base_path}/processed/{media_id}.{format}",
            "url": f"https://storage.wisr.com/{media_id}?token={uuid.uuid4().hex[:8]}",
            "public_url": None
        }

    def generate_weather_data(self, capture_date):
        """Generate random weather data for the given date"""
        condition = random.choice(WEATHER_CONDITIONS)
        is_day = 6 <= capture_date.hour < 20
        icon = condition["icon"]
        if not is_day:
            # Replace day with night icon (d -> n)
            icon = icon[:-1] + "n"
        
        # Generate temperature based on time of day and random variance
        base_temp = 70  # Default base temperature
        
        # Time of day adjustment
        hour = capture_date.hour
        if 0 <= hour < 6:  # Late night
            base_temp -= 10
        elif 6 <= hour < 12:  # Morning
            base_temp -= 5 + (hour - 6)  # Gradually warming
        elif 12 <= hour < 18:  # Afternoon
            base_temp += 5 - (hour - 12) * 0.5  # Peak at noon, cooling gradually
        else:  # Evening
            base_temp -= (hour - 18)  # Cooling down
        
        # Add random variance
        temp = base_temp + random.uniform(-5, 5)
        
        # Calculate other weather metrics
        humidity = random.randint(30, 80)
        pressure = random.randint(1000, 1020)
        
        # Wind data
        wind_speed = random.uniform(0, 15)
        wind_gust = wind_speed + random.uniform(0, 5) if wind_speed > 5 else 0
        wind_direction = random.randint(0, 359)
        
        # Calculate "feels like" temperature
        feels_like = temp - 0.7 * (1 - humidity/100) if temp > 70 else temp + 0.5 * wind_speed if temp < 50 else temp
        
        # Calculate dew point
        dew_point = temp - ((100 - humidity) / 5)
        
        # Generate timestamp with a small delay
        timestamp = capture_date + timedelta(seconds=random.randint(5, 30))
        
        # Sunrise/sunset times
        sunrise_time = datetime(
            capture_date.year, capture_date.month, capture_date.day, 
            7, random.randint(20, 35), random.randint(0, 59),
            tzinfo=capture_date.tzinfo
        )
        sunset_time = datetime(
            capture_date.year, capture_date.month, capture_date.day, 
            19, random.randint(45, 59), random.randint(0, 59),
            tzinfo=capture_date.tzinfo
        )
        
        return {
            "timestamp": timestamp.isoformat(),
            "temperature": round(temp, 2),
            "feels_like": round(feels_like, 2),
            "humidity": humidity,
            "dew_point": round(dew_point, 2),
            "pressure": pressure,
            "wind_speed": round(wind_speed, 2),
            "wind_gust": round(wind_gust, 2),
            "wind_direction": wind_direction,
            "clouds": random.randint(0, 100),
            "visibility": random.randint(5000, 10000),
            "uvi": round(random.uniform(0, 10), 2),
            "conditions": {
                "id": condition["id"],
                "main": condition["main"],
                "description": condition["description"],
                "icon": icon
            },
            "sunrise": sunrise_time.isoformat(),
            "sunset": sunset_time.isoformat(),
            "source": "openweathermap",
            "request_timestamp": (timestamp + timedelta(seconds=random.randint(5, 20))).isoformat()
        }
    
    # METHHOD IS INCOMPLETE
    def generate_astronomical_data(self, capture_date, weather_data):
        """Generate random astronomical data for the given date"""
        # Use sunrise/sunset from weather data
        sunrise = datetime.fromisoformat(weather_data["sunrise"])
        sunset = datetime.fromisoformat(weather_data["sunset"])
        
        # Calculate moon phase
        moon_phase = random.choice(MOON_PHASES)
        illumination = random.uniform(0, 1)
        if moon_phase == "New Moon":
            illumination = random.uniform(0, 0.05)
        elif moon_phase == "First Quarter" or moon_phase == "Last Quarter":
            illumination = random.uniform(0.45, 0.55)
        elif moon_phase == "Full Moon":
            illumination = random.uniform(0.95, 1.0)
        elif "Crescent" in moon_phase:
            illumination = random.uniform(0.05, 0.45)
        elif "Gibbous" in moon_phase:
            illumination = random.uniform(0.55, 0.95)
        
        # Calculate days since new moon based on phase
        if moon_phase == "New Moon":
            days_since_new = random.uniform(0, 0.5)
        elif moon_phase == "Waxing Crescent":
            days_since_new = random.uniform(0.5, 6.5)
        elif moon_phase == "First Quarter":
            days_since_new = random.uniform(6.5, 8.5)
        elif moon_phase == "Waxing Gibbous":
            days_since_new = random.uniform(8.5, 14)
        elif moon_phase == "Full Moon":
            days_since_new = random.uniform(14, 15.5)
        elif moon_phase == "Waning Gibbous":
            days_since_new = random.uniform(15.5, 21.5)
        elif moon_phase == "Last Quarter":
            days_since_new = random.uniform(21.5, 23.5)
        else:  # Waning Crescent
            days_since_new = random.uniform(23.5, 29)
        
        # Determine sun position based on time
        hour = capture_date.hour
        sun_position = self.get_sun_position(hour)
        
        # Calculate altitude and azimuth for sun and moon
        # Simplified calculations - not astronomically accurate
        time_of_day_normalized = (hour + capture_date.minute / 60) / 24  # 0 to 1
        sun_altitude = -90 + 180 * math.sin(math.pi * time_of_day_normalized)  # -90 to 90
        
        # Adjust for day/night
        if sun_position == "night":
            sun_altitude = min(sun_altitude, -0.5)  # Below horizon
        elif sun_position == "dawn":
            sun_altitude = random.uniform(-5, 5)  # Around horizon
        elif sun_position == "dusk":
            sun_altitude = random.uniform(-5, 5)  # Around horizon
        
        # Sun azimuth changes throughout the day (East to West)
        sun_azimuth = 90 + 180 * time_of_day_normalized  # 90 (East) to 270 (West)
        
        # Moon calculations (simplified)
        moon_offset = days_since_new / 29.5 * 360  # 0 to 360 degrees
        moon_time_offset = (moon_offset / 360) * 24  # 0 to 24 hours
        moon_time = (time_of_day_normalized * 24 + moon_time_offset) % 24  # 0 to 24
        moon_altitude = -90 + 180 * math.sin(math.pi * moon_time / 24)
        moon_azimuth = 90 + 180 * (moon_time / 24)
        
        # Generate moonrise and moonset times
        moonrise_hour = (sunrise.hour + 12 + random.randint(-2, 2)) % 24
        moonrise = datetime(
            capture_date.year, capture_date.month, capture_date.day,
            moonrise_hour, random.randint(0, 59), random.randint(0, 59),
            tzinfo=capture_date.tzinfo
        )
        
        # Moonset is approximately 12 hours after moonrise
        moonset = moonrise + timedelta(hours=12, minutes=random.randint(-30, 30))
        
        # Generate feeding times based on moon phase and position
        major_feeding_1_start = moonrise + timedelta(hours=random.randint(0, 2))
        major_feeding_1_end = major_feeding_1_start + timedelta(hours=2)
        
        major_feeding_2_start = moonset + timedelta(hours=random.randint(-2, 0))
        major_feeding_2_end = major_feeding_2_start + timedelta(hours=2)
        
        minor_feeding_1_start = major_feeding_1_start - timedelta(hours=5, minutes=30)
        minor_feeding_1_end = minor_feeding_1_start + timedelta(hours=1)
        
        minor_feeding_2_start = major_feeding_2_start - timedelta(hours=5, minutes=30)
        minor_feeding_2_end = minor_feeding_2_start + timedelta(hours=1)
        
        return {
            "sun": {
                "position": sun_position,
                "altitude": round(sun_altitude, 2),
                "azimuth": round(sun_azimuth, 2),
                "sunrise": weather_data["sunrise"],
                "sunset": weather_data["sunset"]
            },
            "moon": {
                "phase": moon_phase,
                "illumination": round(illumination, 3),
                "days_since_new_moon": round(days_since_new, 1),
                "altitude": round(moon_altitude, 2),
                "azimuth": round(moon_azimuth, 2),
                "distance": round(220000 + random.uniform(0, 10000), 2),
                "moonrise": moonrise.isoformat(),
                "moonset": moonset.isoformat()
            },
            "feeding": {
                "major": [
                    {
                        "start_timestamp": major_feeding_1_start.isoformat(),
                        "end_timestamp": major_feeding_1_end.isoformat()
                    },
                    {
                        "start_timestamp": major_feeding_2_start.isoformat(),
                        "end_timestamp": major_feeding_2_end.isoformat()
                    }
                ],
                "minor": [
                    {
                        "start_timestamp": minor_feeding_1_start.isoformat(),
                        "end_timestamp": minor_feeding_1_end.isoformat()
                    },
                    {
                        "start_timestamp": minor_feeding_2_start.isoformat(),
                        "end_timestamp": minor_feeding_2_end.isoformat()
                    }
                ]
            },
            "source": "skyfield",
            "request_timestamp": (datetime.fromisoformat(weather_data["request_timestamp"]) + 
                            timedelta(seconds=random.randint(2, 10))).isoformat()
        }


    def generate_enrichment_processes(self, media_id, capture_date, detection_data):
        """Generate enrichment process tracking data"""
        processes = []
        
        # Start time for first process
        start_time = capture_date + timedelta(seconds=random.randint(10, 30))
        
        # Weather enrichment process
        weather_duration = random.uniform(0.5, 2.0)
        weather_process = {
            "process_id": f"weather-{uuid.uuid4().hex[:8]}",
            "type": "weather",
            "status": random.choices(["success", "failed"], weights=[0.95, 0.05], k=1)[0],
            "started_timestamp": start_time.isoformat(),
            "completed_timestamp": (start_time + timedelta(seconds=weather_duration)).isoformat(),
            "duration_ms": int(weather_duration * 1000),
            "version": "1.2.3",
            "model": None,
            "service": "openweathermap",
            "priority": "high",
            "errors": None,
            "input_parameters": {
                "media_id": media_id,
                "coordinates": [random.uniform(-99.7, -99.5), random.uniform(30.9, 31.1)]
            },
            "output_summary": None
        }
        
        # Add error data if process failed
        if weather_process["status"] == "failed":
            weather_process["errors"] = "API connection timeout"
        
        processes.append(weather_process)
        
        # Next process starts after the first
        start_time = datetime.fromisoformat(weather_process["completed_timestamp"]) + timedelta(seconds=random.randint(1, 5))
        
        # Astronomical enrichment process
        astro_duration = random.uniform(0.3, 1.5)
        astro_process = {
            "process_id": f"astro-{uuid.uuid4().hex[:8]}",
            "type": "astronomical",
            "status": random.choices(["success", "failed"], weights=[0.98, 0.02], k=1)[0],
            "started_timestamp": start_time.isoformat(),
            "completed_timestamp": (start_time + timedelta(seconds=astro_duration)).isoformat(),
            "duration_ms": int(astro_duration * 1000),
            "version": "1.1.5",
            "model": None,
            "service": "skyfield",
            "priority": "medium",
            "errors": None,
            "input_parameters": {
                "media_id": media_id,
                "capture_timestamp": capture_date.isoformat()
            },
            "output_summary": None
        }
        
        # Add error data if process failed
        if astro_process["status"] == "failed":
            astro_process["errors"] = "Calculation error for moon position"
        
        processes.append(astro_process)
        
        # Next process starts after the second
        start_time = datetime.fromisoformat(astro_process["completed_timestamp"]) + timedelta(seconds=random.randint(1, 5))
        
        # Object detection process
        detection_duration = random.uniform(1.2, 4.0)
        detection_process = {
            "process_id": f"detect-{uuid.uuid4().hex[:8]}",
            "type": "object-detection",
            "status": random.choices(["success", "partial", "failed"], weights=[0.94, 0.04, 0.02], k=1)[0],
            "started_timestamp": start_time.isoformat(),
            "completed_timestamp": (start_time + timedelta(seconds=detection_duration)).isoformat(),
            "duration_ms": int(detection_duration * 1000),
            "version": "3.2.1",
            "model": "wildlife-detector-v3",
            "service": "AI-detection-service",
            "priority": "high",
            "errors": None,
            "input_parameters": {
                "media_id": media_id,
                "confidence_threshold": 0.6,
                "use_enhanced_model": True
            },
            "output_summary": {
                "objects_detected": len(detection_data.get("objects", [])),
                "primary_class": detection_data.get("summary", {}).get("class_distribution", {}).get("primary_class")
            }
        }
        
        # Add error data if process failed or partial
        if detection_process["status"] == "failed":
            detection_process["errors"] = "Model loading error"
            detection_process["output_summary"] = None
        elif detection_process["status"] == "partial":
            detection_process["errors"] = "Low confidence on some detections"
        
        processes.append(detection_process)
        
        # Add video processing for videos
        if random.random() < 0.2:  # 20% chance of having video processing
            # Next process starts after the third
            start_time = datetime.fromisoformat(detection_process["completed_timestamp"]) + timedelta(seconds=random.randint(1, 5))
            
            video_duration = random.uniform(3.0, 8.0)
            video_process = {
                "process_id": f"video-{uuid.uuid4().hex[:8]}",
                "type": "video-processing",
                "status": random.choices(["success", "failed"], weights=[0.9, 0.1], k=1)[0],
                "started_timestamp": start_time.isoformat(),
                "completed_timestamp": (start_time + timedelta(seconds=video_duration)).isoformat(),
                "duration_ms": int(video_duration * 1000),
                "version": "2.0.4",
                "model": "motion-tracker-v2",
                "service": "video-analysis-service",
                "priority": "low",
                "errors": None,
                "input_parameters": {
                    "media_id": media_id,
                    "extract_frames": True,
                    "track_objects": True
                },
                "output_summary": {
                    "frames_processed": random.randint(50, 200),
                    "tracking_success": True
                }
            }
            
            # Add error data if process failed
            if video_process["status"] == "failed":
                video_process["errors"] = "Video codec not supported"
                video_process["output_summary"] = None
            
            processes.append(video_process)
        
        return processes                        
    
    def generate_wildlife_detection(self, width, height, is_video=False, frame_number=None):
        """Generate wildlife detection data"""
        wildlife_type = random.choice(WILDLIFE_TYPES)
        
        # Generate bounding box
        box_width = int(width * random.uniform(0.15, 0.3))
        box_height = int(height * random.uniform(0.15, 0.4))
        box_x = int(random.uniform(0.1, 0.9) * (width - box_width))
        box_y = int(random.uniform(0.1, 0.9) * (height - box_height))
        
        # Select attributes
        sex = random.choice(wildlife_type["sex_options"])
        age = random.choice(wildlife_type["age_options"])
        action = random.choice(wildlife_type["action_options"])
        color = random.choice(wildlife_type["color_options"])
        size = random.choice(wildlife_type["size_options"])
        
        # Confidence score
        confidence = random.uniform(0.7, 0.98)
        
        # Determine if object has identification
        has_id = random.random() < 0.2 and sex is not None
        identification = None
        
        if has_id and sex in wildlife_type["identified_names"]:
            id_name = random.choice(wildlife_type["identified_names"][sex])
            id_confidence = random.uniform(0.7, 0.9)
            history = [f"media-{uuid.uuid4().hex[:6]}" for _ in range(random.randint(1, 3))]
            identification = {
                "name": id_name,
                "id": f"{wildlife_type['class']}-{random.randint(1, 999):03d}",
                "confidence": round(id_confidence, 2),
                "first_seen": (datetime.now(timezone.utc) - timedelta(days=random.randint(10, 100))).isoformat(),
                "last_seen": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 9))).isoformat(),
                "historical_matches": random.randint(3, 15),
                "match_media_ids": history,
                "notes": f"Regular {wildlife_type['class']} in the area"
            }
        
        # Add video-specific fields if this is a video
        tracking_data = None
        if is_video:
            tracking_id = f"track-{uuid.uuid4().hex[:6]}"
            detection_id = f"det-{uuid.uuid4().hex[:8]}"
            
            # Only add frame number if provided
            frame_data = {}
            if frame_number is not None:
                frame_data["frame_number"] = frame_number
            
            # Add time data
            now = datetime.now(timezone.utc)
            appearance_timestamp = now - timedelta(seconds=random.randint(10, 30))
            disappearance_timestamp = appearance_timestamp + timedelta(seconds=random.uniform(3, 15))
            
            tracking_data = {
                "tracking_id": tracking_id,
                "detection_id": detection_id,
                **frame_data,
                "appearance_timestamp": appearance_timestamp.isoformat(),
                "disappearance_timestamp": disappearance_timestamp.isoformat(),
                "duration_ms": int((disappearance_timestamp - appearance_timestamp).total_seconds() * 1000),
                "motion": {
                    "direction": random.choice(["left", "right", "stationary", "towards", "away"]),
                    "speed": random.uniform(0, 5),
                    "is_stationary": random.random() < 0.3,
                    "path": [
                        [random.uniform(-99.61, -99.60), random.uniform(30.99, 31.00)]
                    ]
                }
            }
        
        # Create object data
        obj = {
            "category": "wildlife",
            "class": wildlife_type["class"],
            "subclass": wildlife_type["subclass"],
            "confidence": round(confidence, 2),
            "count": 1,  # Each object represents 1 animal
            "bounding_box": {
                "x": box_x,
                "y": box_y,
                "width": box_width,
                "height": box_height
            },
            "attributes": {
                "sex": sex,
                "age": age,
                "action": action,
                "color": color,
                "size": size,
                "position": random.choice(["center", "left", "right", "background", "foreground"]),
                "occlusion": random.uniform(0, 0.4) if random.random() < 0.3 else 0,
                "blur": random.uniform(0, 0.3) if random.random() < 0.2 else 0
            },
            "taxonomic": wildlife_type["taxonomic"]
        }
        
        # Add motion tracking if it's a video
        if tracking_data:
            obj.update(tracking_data)
        
        # Add antler points for bucks
        if wildlife_type["class"] == "deer" and sex == "buck" and age in ["mature", "adult"]:
            obj["attributes"]["antler_points"] = random.randint(6, 12)
            obj["attributes"]["antler_spread"] = random.uniform(15, 22)
            obj["attributes"]["body_condition"] = random.choice(["fair", "good", "excellent"])
            
            # Add some distinctive features
            if random.random() < 0.3:
                obj["attributes"]["distinctive_features"] = random.choice(["drop tine", "kicker", "sticker", "split G2", "non-typical"])
        
        # Add group size for deer
        if wildlife_type["class"] == "deer" and random.random() < 0.4:
            obj["attributes"]["group_size"] = random.randint(2, 8)
            
            # Add with_young for does
            if sex == "doe" and random.random() < 0.6:
                obj["attributes"]["with_young"] = True
        
        # Add identification if present
        if identification:
            obj["identification"] = identification
        
        # Add relations (10% chance)
        if random.random() < 0.1:
            obj["relations"] = [
                {
                    "related_to": f"det-{uuid.uuid4().hex[:8]}",
                    "relation_type": random.choice(["parent-of", "offspring-of", "group-with"]),
                    "confidence": random.uniform(0.6, 0.9)
                }
            ]
        
        return obj, wildlife_type["class"]
    
    def generate_person_detection(self, width, height, is_video=False, frame_number=None):
        """Generate person detection data"""
        # Select attributes
        eclass = random.choice(PERSON_TYPES["class"])
        subclass = random.choice(PERSON_TYPES["subclass"])
        gender = random.choice(PERSON_TYPES["gender_options"])
        age_range = random.choice(PERSON_TYPES["age_range_options"])
        action = random.choice(PERSON_TYPES["action_options"])
        posture = random.choice(PERSON_TYPES["posture_options"])
        build = random.choice(PERSON_TYPES["build_options"])
        
        # Select clothing
        upper_body = random.choice(PERSON_TYPES["clothing"]["upper_body"])
        lower_body = random.choice(PERSON_TYPES["clothing"]["lower_body"])
        headwear = random.choice(PERSON_TYPES["clothing"]["headwear"])
        upper_color = random.choice(PERSON_TYPES["color_options"])
        lower_color = random.choice(PERSON_TYPES["color_options"])
        
        # Accessories and what they're carrying
        accessories = random.choice(PERSON_TYPES["accessories_options"])
        carrying = random.choice(PERSON_TYPES["carrying_options"])
        
        # Generate bounding box
        box_width = int(width * random.uniform(0.08, 0.25))
        box_height = int(height * random.uniform(0.2, 0.8))
        box_x = int(random.uniform(0.1, 0.9) * (width - box_width))
        box_y = int(random.uniform(0.1, 0.9) * (height - box_height))
        
        # Confidence score
        confidence = random.uniform(0.7, 0.95)
        
        # Add video-specific fields if this is a video
        tracking_data = None
        if is_video:
            tracking_id = f"track-{uuid.uuid4().hex[:6]}"
            detection_id = f"det-{uuid.uuid4().hex[:8]}"
            
            # Only add frame number if provided
            frame_data = {}
            if frame_number is not None:
                frame_data["frame_number"] = frame_number
            
            # Add time data
            now = datetime.now(timezone.utc)
            appearance_timestamp = now - timedelta(seconds=random.randint(10, 30))
            disappearance_timestamp = appearance_timestamp + timedelta(seconds=random.uniform(3, 15))
            
            tracking_data = {
                "tracking_id": tracking_id,
                "detection_id": detection_id,
                **frame_data,
                "appearance_timestamp": appearance_timestamp.isoformat(),
                "disappearance_timestamp": disappearance_timestamp.isoformat(),
                "duration_ms": int((disappearance_timestamp - appearance_timestamp).total_seconds() * 1000),
                "motion": {
                    "direction": random.choice(["left", "right", "stationary", "towards", "away"]),
                    "speed": random.uniform(0, 3),
                    "is_stationary": random.random() < 0.4,
                    "path": [
                        [random.uniform(-99.61, -99.60), random.uniform(30.99, 31.00)]
                    ]
                }
            }
        
        # Create object data
        obj = {
            "category": "person",
            "class": eclass,
            "subclass": subclass,
            "confidence": round(confidence, 2),
            "count": 1,
            "bounding_box": {
                "x": box_x,
                "y": box_y,
                "width": box_width,
                "height": box_height
            },
            "attributes": {
                "gender": gender,
                "age_range": age_range,
                "action": action,
                "posture": posture,
                "height": random.choice(["short", "average", "tall"]),
                "build": build,
                "clothing": {
                    "upper_body": upper_body,
                    "lower_body": lower_body,
                    "headwear": headwear,
                    "colors": [upper_color, lower_color]
                },
                "position": random.choice(["center", "left", "right", "background", "foreground"]),
                "occlusion": random.uniform(0, 0.4) if random.random() < 0.3 else 0,
                "blur": random.uniform(0, 0.3) if random.random() < 0.2 else 0
            }
        }
        
        # Add accessories and carrying if present
        if accessories:
            obj["attributes"]["accessories"] = accessories
        if carrying:
            obj["attributes"]["carrying"] = carrying
        
        # Add motion tracking if it's a video
        if tracking_data:
            obj.update(tracking_data)
        
        # Add identification (5% chance for people)
        if random.random() < 0.05:
            obj["identification"] = {
                "name": f"Person {random.randint(1, 100)}",
                "id": f"person-{random.randint(1, 999):03d}",
                "confidence": round(random.uniform(0.7, 0.9), 2),
                "first_seen": (datetime.now(timezone.utc) - timedelta(days=random.randint(10, 100))).isoformat(),
                "last_seen": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 9))).isoformat(),
                "historical_matches": random.randint(1, 8),
                "match_media_ids": [f"media-{uuid.uuid4().hex[:6]}" for _ in range(random.randint(1, 3))],
                "notes": f"Regular visitor to the property"
            }
        
        # return obj, "person"
        return obj, obj["class"]
    
    def generate_vehicle_detection(self, width, height, is_video=False, frame_number=None):
        """Generate vehicle detection data"""
        # Select vehicle type
        subclass = random.choice(VEHICLE_TYPES["subclass"])
        make = random.choice(VEHICLE_TYPES["make_options"])
        
        # Select model based on make
        if make in VEHICLE_TYPES["model_options"]:
            model = random.choice(VEHICLE_TYPES["model_options"][make])
        else:
            model = "Unknown"
        
        # Select other attributes
        color = random.choice(VEHICLE_TYPES["color_options"])
        year_range = random.choice(VEHICLE_TYPES["year_range_options"])
        action = random.choice(VEHICLE_TYPES["action_options"])
        distinctive_marks = random.choice(VEHICLE_TYPES["distinctive_marks_options"])
        
        # Select wheels and doors based on subclass
        if subclass in ["motorcycle"]:
            wheels = 2
            doors = 0
        elif subclass in ["atv", "utility vehicle"]:
            wheels = 4
            doors = 0
        else:
            wheels = random.choice(VEHICLE_TYPES["wheels_options"])
            doors = random.choice(VEHICLE_TYPES["doors_options"])
        
        # Generate bounding box
        box_width = int(width * random.uniform(0.15, 0.4))
        box_height = int(height * random.uniform(0.15, 0.3))
        box_x = int(random.uniform(0.1, 0.9) * (width - box_width))
        box_y = int(random.uniform(0.1, 0.9) * (height - box_height))
        
        # Confidence score
        confidence = random.uniform(0.7, 0.95)
        
        # Add video-specific fields if this is a video
        tracking_data = None
        if is_video:
            tracking_id = f"track-{uuid.uuid4().hex[:6]}"
            detection_id = f"det-{uuid.uuid4().hex[:8]}"
            
            # Only add frame number if provided
            frame_data = {}
            if frame_number is not None:
                frame_data["frame_number"] = frame_number
            
            # Add time data
            now = datetime.now(timezone.utc)
            appearance_timestamp = now - timedelta(seconds=random.randint(10, 30))
            disappearance_timestamp = appearance_timestamp + timedelta(seconds=random.uniform(3, 15))
            
            tracking_data = {
                "tracking_id": tracking_id,
                "detection_id": detection_id,
                **frame_data,
                "appearance_timestamp": appearance_timestamp.isoformat(),
                "disappearance_timestamp": disappearance_timestamp.isoformat(),
                "duration_ms": int((disappearance_timestamp - appearance_timestamp).total_seconds() * 1000),
                "motion": {
                    "direction": random.choice(["left", "right", "stationary", "towards", "away"]),
                    "speed": random.uniform(0, 15) if action == "moving" else 0,
                    "is_stationary": action != "moving",
                    "path": [
                        [random.uniform(-99.61, -99.60), random.uniform(30.99, 31.00)]
                    ]
                }
            }
        
        # Determine if license plate is detected (20% chance)
        license_plate = None
        if random.random() < 0.2:
            license_plate = f"{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}" + \
                            f"{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}" + \
                            f"{random.randint(0, 9)}{random.randint(0, 9)}" + \
                            f"{random.randint(0, 9)}{random.randint(0, 9)}"
        
        # Create object data
        obj = {
            "category": "vehicle",
            "class": "vehicle",
            "subclass": subclass,
            "confidence": round(confidence, 2),
            "count": 1,
            "bounding_box": {
                "x": box_x,
                "y": box_y,
                "width": box_width,
                "height": box_height
            },
            "attributes": {
                "vehicle_type": subclass,
                "make": make,
                "model": model,
                "color": color,
                "year_range": year_range,
                "position": random.choice(["center", "left", "right", "background", "foreground"]),
                "occlusion": random.uniform(0, 0.4) if random.random() < 0.3 else 0,
                "blur": random.uniform(0, 0.3) if random.random() < 0.2 else 0,
                "wheels": wheels,
                "doors": doors,
                "is_moving": action == "moving",
                "lights_on": random.random() < 0.3
            }
        }
        
        # Add license plate if detected
        if license_plate:
            obj["attributes"]["license_plate"] = license_plate
            obj["attributes"]["state"] = random.choice(["TX", "OK", "LA", "NM", "AR"])
        
        # Add distinctive marks if present
        if distinctive_marks:
            obj["attributes"]["distinctive_marks"] = distinctive_marks
        
        # Add occupants count if relevant
        if subclass not in ["motorcycle", "atv"] and random.random() < 0.6:
            obj["attributes"]["occupants"] = random.randint(1, 5)
        
        # Add motion tracking if it's a video
        if tracking_data:
            obj.update(tracking_data)
        
        # Add direction of travel for moving vehicles
        if action == "moving":
            obj["attributes"]["direction_of_travel"] = random.choice(["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"])
        
        return obj, "vehicle"
    
    def generate_enhanced_detection_data(self, media_type, resolution_key, capture_date, sun_position):
        """Generate random object detection data with support for wildlife, people, and vehicles"""
        # Width and height from resolution
        width, height, _ = RESOLUTIONS[resolution_key]
        
        # Determine what kind of detection to generate
        detection_roll = random.random()
        
        # Accumulate probabilities
        wildlife_threshold = self.wildlife_probability
        people_threshold = wildlife_threshold + self.people_probability
        vehicle_threshold = people_threshold + self.vehicle_probability
        # Remaining probability is empty_probability
        
        # Initialize return structure
        is_video = media_type == "video"
        
        # Common event detection fields
        event_data = None
        if is_video and random.random() < 0.3:  # 30% chance of having event detection for videos
            event_type = random.choice(["passing", "feeding", "resting", "hunting", "interaction"])
            event_data = {
                "type": event_type,
                "confidence": round(random.uniform(0.7, 0.95), 2),
                "start_timestamp": (capture_date - timedelta(seconds=random.randint(1, 10))).isoformat(),
                "end_timestamp": (capture_date + timedelta(seconds=random.randint(5, 30))).isoformat(),
                "duration_ms": random.randint(6000, 40000),
                "primary_objects": [],  # Will be filled later
                "secondary_objects": [],  # Will be filled later if applicable
                "description": f"{event_type.capitalize()} event detected",
                "significance": random.choice(["low", "medium", "high"])
            }
        
        # Initialize detection summary
        summary = {
            "total_objects": 0,
            "empty_frame": True,
            "contains_wildlife": False,
            "contains_people": False,
            "contains_vehicles": False,
            "contains_other": False,
            "contains_known_individuals": False,
            "named_individuals": [],
            "object_counts": {
                "wildlife": 0,
                "people": 0,
                "vehicles": 0,
                "other": 0
            },
            "class_distribution": {
                "primary_class": None,
                "primary_confidence": None,
                "classes": [],
                "subclasses": [],
                "class_counts": {}
            },
            "motion_summary": {
                "predominant_direction": None,
                "activity_level": "none",
                "entry_points": [],
                "exit_points": []
            },
            "scene_context": {
                "time_of_day": sun_position,
                "lighting_conditions": "good" if sun_position in ["day"] else "low" if sun_position in ["dawn", "dusk"] else "poor",
                "weather_apparent": random.choice(["clear", "cloudy", "rainy", "foggy"]),
                "terrain": random.choice(["field", "forest", "road", "trail", "water"]),
                "habitat": random.choice(["grassland", "woodland", "wetland", "mixed"]),
                "is_feeding_area": random.random() < 0.3,
                "is_water_source": random.random() < 0.2,
                "is_trail": random.random() < 0.4,
                "is_road": random.random() < 0.2,
                "is_boundary": random.random() < 0.15
            }
        }
        
        # Empty detection
        if detection_roll > vehicle_threshold:
            # No detections - return empty result
            return {
                "objects": [],
                "summary": summary,
                "event": event_data,
                "processing": {
                    "model": "multi-detector-v3",
                    "version": "3.2.1",
                    "processing_time_ms": round(random.uniform(150, 300)),
                    "timestamp": (capture_date + timedelta(seconds=random.randint(30, 60))).isoformat(),
                    "confidence_threshold": 0.65,
                    "processor_id": f"proc-{uuid.uuid4().hex[:8]}",
                    "batch_id": f"batch-{uuid.uuid4().hex[:8]}",
                    "models_used": ["base-detector-v3"],
                    "is_reprocessed": random.random() < 0.05,
                    "parameters": {
                        "min_confidence": 0.65,
                        "include_tracking": is_video
                    }
                }
            }
        
        # Determine number of objects
        min_objects = 1
        max_objects = 3
        
        # Higher probability of multiple objects in videos
        if is_video:
            max_objects = 5
        
        # Adjust for time of day - more wildlife at dawn/dusk
        if sun_position in ["dawn", "dusk"]:
            min_objects = max(1, min_objects)
            max_objects = max(3, max_objects)
        
        num_objects = random.randint(min_objects, max_objects)
        
        # Generate objects
        objects = []
        all_classes = []
        all_subclasses = []
        
        # Main detection type
        if detection_roll < wildlife_threshold:
            # Wildlife detection
            main_type = "wildlife"
        elif detection_roll < people_threshold:
            # Person detection
            main_type = "person"
        else:
            # Vehicle detection
            main_type = "vehicle"
        
        # Generate objects
        for i in range(num_objects):
            # For first object use selected type, for others maybe mix
            detection_type = main_type
            if i > 0 and random.random() < 0.3:  # 30% chance to mix object types
                detection_type = random.choices(
                    ["wildlife", "person", "vehicle"], 
                    weights=[0.6, 0.3, 0.1], 
                    k=1
                )[0]
            
            # Generate object based on type
            if detection_type == "wildlife":
                obj, obj_class = self.generate_wildlife_detection(width, height, is_video)
                summary["contains_wildlife"] = True
                summary["object_counts"]["wildlife"] += 1
            elif detection_type == "person":
                obj, obj_class = self.generate_person_detection(width, height, is_video)
                summary["contains_people"] = True
                summary["object_counts"]["people"] += 1
            else:  # vehicle
                obj, obj_class = self.generate_vehicle_detection(width, height, is_video)
                summary["contains_vehicles"] = True
                summary["object_counts"]["vehicles"] += 1
            
            # Add to lists
            objects.append(obj)
            all_classes.append(obj_class)
            if obj.get("subclass"):
                all_subclasses.append(obj["subclass"])
            
            # Check for named individuals
            if "identification" in obj and obj["identification"]:
                summary["contains_known_individuals"] = True
                if obj["identification"]["name"] not in summary["named_individuals"]:
                    summary["named_individuals"].append(obj["identification"]["name"])
            
            # Add to primary/secondary objects for events
            if event_data:
                if i == 0:
                    event_data["primary_objects"].append(obj_class)
                else:
                    event_data["secondary_objects"].append(obj_class)
        
        # Update summary
        summary["total_objects"] = len(objects)
        summary["empty_frame"] = len(objects) == 0
        
        # Primary class is the most common class
        if all_classes:
            class_counts = {}
            for cls in all_classes:
                class_counts[cls] = class_counts.get(cls, 0) + 1
            
            primary_class = max(class_counts.items(), key=lambda x: x[1])[0]
            # primary_confidence = max([obj["confidence"] for obj in objects if obj["class"] == primary_class])
            primary_confidence = max([
                obj["confidence"] for obj in objects 
                if (obj["class"] == primary_class) or 
                (isinstance(obj["class"], list) and primary_class in obj["class"])
            ])
            
            summary["class_distribution"]["primary_class"] = primary_class
            summary["class_distribution"]["primary_confidence"] = primary_confidence
            summary["class_distribution"]["classes"] = list(set(all_classes))
            summary["class_distribution"]["subclasses"] = list(set(all_subclasses))
            summary["class_distribution"]["class_counts"] = class_counts
        
        # Update motion summary for videos
        if is_video and objects:
            directions = []
            for obj in objects:
                if "motion" in obj and "direction" in obj["motion"]:
                    directions.append(obj["motion"]["direction"])
            
            if directions:
                # Count occurrences of each direction
                direction_counts = {}
                for direction in directions:
                    direction_counts[direction] = direction_counts.get(direction, 0) + 1
                
                # Get the most common direction
                predominant_direction = max(direction_counts.items(), key=lambda x: x[1])[0]
                
                # Update motion summary
                summary["motion_summary"]["predominant_direction"] = predominant_direction
                summary["motion_summary"]["activity_level"] = "high" if len(objects) > 2 else "medium" if len(objects) > 1 else "low"
                
                # Add entry/exit points based on directions
                if "towards" in directions:
                    summary["motion_summary"]["entry_points"].append("front")
                if "away" in directions:
                    summary["motion_summary"]["exit_points"].append("back")
                if "left" in directions:
                    summary["motion_summary"]["entry_points"].append("right")
                    summary["motion_summary"]["exit_points"].append("left")
                if "right" in directions:
                    summary["motion_summary"]["entry_points"].append("left")
                    summary["motion_summary"]["exit_points"].append("right")
        
        # Processing metrics
        processing_time = 150 + (num_objects * 75) + random.uniform(0, 100)
        
        return {
            "objects": objects,
            "summary": summary,
            "event": event_data,
            "processing": {
                "model": "multi-detector-v3",
                "version": "3.2.1",
                "processing_time_ms": round(processing_time),
                "timestamp": (capture_date + timedelta(seconds=random.randint(30, 60))).isoformat(),
                "confidence_threshold": 0.65,
                "processor_id": f"proc-{uuid.uuid4().hex[:8]}",
                "batch_id": f"batch-{uuid.uuid4().hex[:8]}",
                "models_used": [
                    "base-detector-v3", 
                    "wildlife-classifier-v2" if summary["contains_wildlife"] else None,
                    "person-detector-v2" if summary["contains_people"] else None,
                    "vehicle-detector-v1" if summary["contains_vehicles"] else None
                ],
                "is_reprocessed": random.random() < 0.05,
                "parameters": {
                    "min_confidence": 0.65,
                    "include_tracking": is_video,
                    "detect_wildlife": True,
                    "detect_people": True,
                    "detect_vehicles": True
                }
            }
        }
    
    def generate_enhanced_tags(self, detection_data, weather_data, astronomical_data, media_type):
        """Generate tags based on enhanced detection, weather, and time"""
        tags = {
            "system": [],
            "user": [],
            "ai": []
        }
        
        # Add basic system tags
        tags["system"].append(media_type)
        
        # Add time-related tags
        sun_position = astronomical_data["sun"]["position"]
        tags["system"].append(sun_position)
        
        # Add weather tags
        weather_condition = weather_data["conditions"]["main"].lower()
        tags["system"].append(f"{weather_condition}-weather")
        
        if weather_data["temperature"] < 50:
            tags["system"].append("cold")
        elif weather_data["temperature"] > 80:
            tags["system"].append("hot")
        
        if weather_data["humidity"] > 70:
            tags["system"].append("humid")
        
        # Add trigger tag
        tags["system"].append("motion")
        
        # Add empty tag if no objects detected
        if detection_data["summary"]["empty_frame"]:
            tags["system"].append("empty")
            return tags
        
        # Add detection-based tags
        contains_wildlife = detection_data["summary"]["contains_wildlife"]
        contains_people = detection_data["summary"]["contains_people"]
        contains_vehicles = detection_data["summary"]["contains_vehicles"]
        
        # Add primary class tags
        primary_class = detection_data["summary"]["class_distribution"]["primary_class"]
        if primary_class:
            tags["system"].append(primary_class)
        
        # Add object class tags
        for class_name in detection_data["summary"]["class_distribution"]["classes"]:
            if class_name not in tags["system"]:
                tags["system"].append(class_name)
        
        # Add specific tags based on object types
        for obj in detection_data["objects"]:
            obj_class = obj["class"]
            
            # Add subclass if available
            if obj.get("subclass") and obj["subclass"] not in tags["ai"]:
                tags["ai"].append(obj["subclass"])
            
            # Wildlife-specific tags
            if obj_class in [w["class"] for w in WILDLIFE_TYPES]:
                # Add sex tag
                if obj["attributes"].get("sex") and obj["attributes"]["sex"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["sex"])
                
                # Add age tag
                if obj["attributes"].get("age") and obj["attributes"]["age"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["age"])
                
                # Add action tag
                if obj["attributes"].get("action") and obj["attributes"]["action"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["action"])
                
                # Add antler points for deer
                if obj_class == "deer" and "antler_points" in obj["attributes"]:
                    tags["ai"].append(f"{obj['attributes']['antler_points']}-point")
                
                # Add distinctive features
                if obj["attributes"].get("distinctive_features") and obj["attributes"]["distinctive_features"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["distinctive_features"])
                
                # Add group tag
                if obj["attributes"].get("group_size") and obj["attributes"]["group_size"] > 1:
                    tags["ai"].append("group")
                
                # Add with young tag
                if obj["attributes"].get("with_young"):
                    tags["ai"].append("with-young")
            
            # Person-specific tags
            elif obj_class == "person":
                # Add gender tag if available
                if obj["attributes"].get("gender") and obj["attributes"]["gender"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["gender"])
                
                # Add age range tag if available
                if obj["attributes"].get("age_range") and obj["attributes"]["age_range"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["age_range"])
                
                # Add action tag if available
                if obj["attributes"].get("action") and obj["attributes"]["action"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["action"])
                
                # Add clothing tags
                if "clothing" in obj["attributes"]:
                    for clothing_type in ["headwear", "upper_body", "lower_body"]:
                        if clothing_type in obj["attributes"]["clothing"] and obj["attributes"]["clothing"][clothing_type]:
                            tags["ai"].append(obj["attributes"]["clothing"][clothing_type])
            
            # Vehicle-specific tags
            elif obj_class == "vehicle":
                # Add vehicle type tag
                if obj["attributes"].get("vehicle_type") and obj["attributes"]["vehicle_type"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["vehicle_type"])
                
                # Add make tag
                if obj["attributes"].get("make") and obj["attributes"]["make"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["make"].lower())
                
                # Add color tag
                if obj["attributes"].get("color") and obj["attributes"]["color"] not in tags["ai"]:
                    tags["ai"].append(obj["attributes"]["color"])
                
                # Add movement tag
                if obj["attributes"].get("is_moving"):
                    tags["ai"].append("moving-vehicle")
                else:
                    tags["ai"].append("stationary-vehicle")
            
            # Add identification to AI tags
            if "identification" in obj and obj["identification"]:
                id_name = obj["identification"]["name"].lower().replace(" ", "-")
                if id_name not in tags["ai"]:
                    tags["ai"].append(id_name)
        
        # Add multi-detection tags
        if detection_data["summary"]["total_objects"] > 1:
            tags["system"].append("multiple")
            
            if contains_wildlife and contains_people:
                tags["system"].append("wildlife-human")
            
            if contains_wildlife and contains_vehicles:
                tags["system"].append("wildlife-vehicle")
            
            if contains_people and contains_vehicles:
                tags["system"].append("human-vehicle")
        
        # Add scene context tags
        if detection_data["summary"].get("scene_context"):
            scene = detection_data["summary"]["scene_context"]
            
            # Add habitat tag
            if scene.get("habitat"):
                tags["ai"].append(scene["habitat"])
            
            # Add special area tags
            if scene.get("is_feeding_area") and scene["is_feeding_area"]:
                tags["ai"].append("feeding-area")
            
            if scene.get("is_water_source") and scene["is_water_source"]:
                tags["ai"].append("water-source")
            
            if scene.get("is_trail") and scene["is_trail"]:
                tags["ai"].append("trail")
            
            if scene.get("is_road") and scene["is_road"]:
                tags["ai"].append("road")
        
        # Add some random user tags (70% chance)
        if random.random() < 0.7:
            num_user_tags = random.randint(1, 4)
            
            # Possible user tag categories
            location_tags = ["north-field", "south-field", "east-feeder", "west-feeder", 
                           "creek-crossing", "north-boundary", "south-boundary", "main-trail",
                           "oak-grove", "pond", "blind-1", "blind-2"]
            
            quality_tags = ["good-photo", "bad-quality", "good-light", "too-dark", "check-later", 
                          "interesting", "favorite"]
            
            # Add detection-based user tags
            detection_user_tags = []
            
            # Wildlife-specific user tags
            if contains_wildlife:
                for obj in detection_data["objects"]:
                    if obj["class"] in [w["class"] for w in WILDLIFE_TYPES]:
                        # Base class
                        if obj["class"] not in detection_user_tags:
                            detection_user_tags.append(obj["class"])
                        
                        # Specific deer attributes
                        if obj["class"] == "deer" and obj["attributes"].get("sex"):
                            if obj["attributes"]["sex"] == "buck":
                                detection_user_tags.extend(["buck", "antlers"])
                            elif obj["attributes"]["sex"] == "doe":
                                detection_user_tags.append("doe")
            
            # Person-specific user tags
            if contains_people:
                detection_user_tags.append("person")
                if detection_data["summary"]["object_counts"]["people"] > 1:
                    detection_user_tags.append("people")
                    
                # Check if hunter
                for obj in detection_data["objects"]:
                    if obj["class"] == "person" and obj["subclass"] == "hunter":
                        detection_user_tags.append("hunter")
            
            # Vehicle-specific user tags
            if contains_vehicles:
                detection_user_tags.append("vehicle")
                
                # Add specific vehicle types
                for obj in detection_data["objects"]:
                    if obj["class"] == "vehicle" and obj["attributes"].get("vehicle_type"):
                        vehicle_type = obj["attributes"]["vehicle_type"]
                        detection_user_tags.append(vehicle_type)
            
            # Select random tags
            selected_tags = []
            
            # Always include at least one location tag
            selected_tags.append(random.choice(location_tags))
            
            # Add detection-based tags (higher probability)
            for tag in detection_user_tags:
                if random.random() < 0.6 and len(selected_tags) < num_user_tags:
                    selected_tags.append(tag)
            
            # Add quality tags
            while len(selected_tags) < num_user_tags:
                quality_tag = random.choice(quality_tags)
                if quality_tag not in selected_tags:
                    selected_tags.append(quality_tag)
            
            # Set user tags
            tags["user"] = selected_tags[:num_user_tags]
        
        return tags
    
    def generate_enhanced_user_metadata(self, detection_data, tags):
        """Generate user metadata including notes, rating, etc. for enhanced detection"""
        # Base rating on detection confidence and tags
        rating = 3  # Default average rating
        
        # Adjust rating based on detection
        if detection_data["summary"]["total_objects"] > 0:
            # Higher rating for multiple detections
            if detection_data["summary"]["total_objects"] > 1:
                rating += 1
            
            # Higher rating for high confidence detections
            primary_confidence = detection_data["summary"]["class_distribution"]["primary_confidence"]
            if primary_confidence and primary_confidence > 0.9:
                rating += 1
            
            # Higher rating for identified animals or interesting combinations
            if detection_data["summary"]["contains_known_individuals"]:
                rating += 1
            
            # Interesting combinations
            if (detection_data["summary"]["contains_wildlife"] and 
                detection_data["summary"]["contains_people"]):
                rating += 1
        else:
            # Lower rating for empty images
            rating -= 1
        
        # Adjust rating based on user tags
        positive_tags = ["good-photo", "good-light", "favorite", "interesting", "good-antlers"]
        negative_tags = ["bad-quality", "too-dark", "blurry"]
        
        for tag in tags["user"]:
            if tag in positive_tags:
                rating += 1
            elif tag in negative_tags:
                rating -= 1
        
        # Ensure rating is between 1 and 5
        rating = max(1, min(5, rating))
        
        # Generate notes
        notes = ""
        
        # Base note on detection content
        if detection_data["summary"]["empty_frame"]:
            notes = random.choice([
                "Empty frame - check camera positioning",
                "No animals detected in this image",
                "False trigger - no wildlife present",
                "Empty capture at "
            ])
        elif detection_data["summary"]["contains_wildlife"]:
            wildlife_class = next((obj["class"] for obj in detection_data["objects"] 
                               if obj["class"] in [w["class"] for w in WILDLIFE_TYPES]), None)
            
            if wildlife_class:
                if rating >= 4:
                    notes = random.choice([
                        f"Great {wildlife_class} shot!",
                        f"Excellent {wildlife_class} capture at ",
                        f"Nice {wildlife_class} activity at ",
                        f"Good example of {wildlife_class} at ",
                        f"Clear view of {wildlife_class} at "
                    ])
                else:
                    notes = random.choice([
                        f"{wildlife_class.capitalize()} detected at ",
                        f"{wildlife_class.capitalize()} activity at ",
                        f"{wildlife_class.capitalize()} sighting at ",
                        f"Routine {wildlife_class} capture at "
                    ])
        elif detection_data["summary"]["contains_people"]:
            if rating >= 4:
                notes = random.choice([
                    "Person clearly visible at ",
                    "Good shot of visitor at ",
                    "Clear image of person at ",
                    "Visitor detected at "
                ])
            else:
                notes = random.choice([
                    "Person detected at ",
                    "Human activity at ",
                    "Visitor at ",
                    "Person present at "
                ])
        elif detection_data["summary"]["contains_vehicles"]:
            vehicle_type = next((obj["subclass"] for obj in detection_data["objects"] 
                              if obj["class"] == "vehicle" and "subclass" in obj), "vehicle")
            
            notes = random.choice([
                f"{vehicle_type.capitalize()} detected at ",
                f"{vehicle_type.capitalize()} at ",
                f"Vehicle traffic at ",
                f"{vehicle_type.capitalize()} passing "
            ])
        else:
            # Generic note
            notes = random.choice([
                "Activity detected at ",
                "Motion trigger at ",
                "Capture from ",
                "Detection at "
            ])
        
        # Add location from tags if available
        location_tags = [tag for tag in tags["user"] if "field" in tag or "feeder" in tag or 
                       "boundary" in tag or "trail" in tag or "crossing" in tag]
        if location_tags:
            location = location_tags[0].replace("-", " ")
            notes += location
        else:
            notes += "camera location"
        
        # Add detection info to notes
        if detection_data["summary"]["total_objects"] > 0:
            detection_notes = []
            
            # Add primary class and count
            if detection_data["summary"]["class_distribution"]["primary_class"]:
                primary_class = detection_data["summary"]["class_distribution"]["primary_class"]
                count = detection_data["summary"]["total_objects"]
                
                if count == 1:
                    detection_notes.append(f"Single {primary_class}")
                else:
                    # Use proper pluralization
                    plural = "people" if primary_class == "person" else f"{primary_class}s"
                    detection_notes.append(f"Group of {count} {plural}")
            
            # Add number of each class if mixed detection
            class_counts = detection_data["summary"]["class_distribution"].get("class_counts", {})
            if len(class_counts) > 1:
                for cls, cnt in class_counts.items():
                    # Skip if already covered in primary class note
                    if cls == primary_class and len(class_counts) > 1:
                        continue
                    
                    # Use proper pluralization
                    plural = "people" if cls == "person" and cnt > 1 else f"{cls}s" if cnt > 1 else cls
                    detection_notes.append(f"{cnt} {plural}")
            
            # Add additional details for certain animals
            for obj in detection_data["objects"]:
                # Add deer antler points
                if obj["class"] == "deer" and obj["attributes"].get("sex") == "buck" and "antler_points" in obj["attributes"]:
                    detection_notes.append(f"{obj['attributes']['antler_points']}-point buck")
                
                # Add identifications
                elif "identification" in obj and obj["identification"]:
                    detection_notes.append(f"{obj['identification']['name']}")
                
                # Add vehicle details
                elif obj["class"] == "vehicle" and obj["attributes"].get("make") and obj["attributes"].get("model"):
                    detection_notes.append(f"{obj['attributes']['make']} {obj['attributes']['model']}")
            
            # Combine notes
            if detection_notes:
                notes += " - " + ", ".join(detection_notes)
        
        # Generate last viewed date (random time after processing)
        days_since_processing = random.randint(0, 7)
        last_viewed = (datetime.now(timezone.utc) - timedelta(days=days_since_processing, 
                                                       hours=random.randint(0, 23),
                                                       minutes=random.randint(0, 59)))
        
        # Determine if favorite based on rating
        is_favorite = rating >= 4 and random.random() < 0.7
        
        return {
            "notes": notes,
            "rating": rating,
            "is_favorite": is_favorite,
            "is_hidden": False,
            "is_archived": False,
            "last_viewed_timestamp": last_viewed.isoformat()
        }
    
    def generate_media_record(self, tenant, property_data, device, index):
        """Generate a complete random media record with enhanced object detection"""
        # Generate a unique media ID
        media_id = f"media-{uuid.uuid4().hex[:6]}"
        
        # Get tenant and property info
        tenant_id = tenant["id"]
        property_id = property_data["id"]
        property_name = property_data["name"]
        property_timezone = property_data.get("timezone", "UTC")
        
        # Get device info
        device_id = device["id"]
        device_name = device["name"]
        
        # Generate asset ID if not in device data
        asset_id = device.get("asset_id", f"asset-{random.randint(1, 999):03d}")
        
        # Random date within range
        capture_date = self.generate_random_date()
        
        # Convert to property timezone for local time if timezone is specified
        try:
            # This is a simplification - in real code you would use proper timezone conversion
            # We're just adding a -05:00 suffix for demonstration
            capture_date_local = capture_date.replace(tzinfo=None).isoformat() + "-05:00"
        except:
            capture_date_local = capture_date.isoformat()
        
        # Random media type (90% images, 10% videos)
        media_type = "image" if random.random() < 0.9 else "video"
        
        # Random resolution
        resolution_key = random.choice(list(RESOLUTIONS.keys()))
        width, height, megapixels = RESOLUTIONS[resolution_key]
        
        # File format based on media type
        file_format = random.choice(IMAGE_FORMATS) if media_type == "image" else random.choice(VIDEO_FORMATS)
        
        # Generate file data
        file_data = {
            "size": random.randint(800000, 10000000),
            "width": width,
            "height": height,
            "megapixels": megapixels,
            "format": file_format,
            "mime_type": MIME_TYPES[file_format],
            "duration": None if media_type == "image" else random.uniform(5, 30),
            "fps": None if media_type == "image" else 30,
            "codec": None if media_type == "image" else random.choice(VIDEO_CODECS),
            "bitrate": None if media_type == "image" else random.randint(8000, 16000)
        }
        
        # Generate timestamps
        upload_date = self.add_timestamp_jitter(capture_date, 20)
        processing_date = self.add_timestamp_jitter(upload_date, 60)
        
        # Generate filename
        filename = self.generate_filename(capture_date, index)
        
        # Generate storage paths
        storage_paths = self.generate_storage_paths(
            tenant_id, property_id, device_id, capture_date, media_id, file_format
        )
        
        # Generate location - use device location with small random offset
        device_location = device.get("location", [-99.6, 31.0])
        location = {
            "coordinates": self.generate_random_location(
                device_location[0], device_location[1]
            ),
            "accuracy": "high",
            "source": "device",
            "boundary_id": device.get("boundary_id", "bound-unknown")
        }

        # Generate device information
        device_data = {
            "id": device_id,
            "name": device_name,
            "make": device.get("make", "Generic"),
            "model": device.get("model", "Trail Camera"),
            "serial_number": device.get("serial_number", f"SN{random.randint(10000, 99999)}"),
            "status": {
                "battery_level": random.randint(55, 95),
                "signal_strength": random.choice(["excellent", "good", "fair", "poor"]),
                "temperature": random.randint(65, 75),
                "storage_remaining": f"{random.randint(8, 32)}GB"
            },
            "settings": {
                "mode": random.choice(TRIGGER_TYPES),
                "sensitivity": random.choice(["low", "medium", "high"]),
                "resolution": resolution_key
            }
        }
        
        # Generate trigger information
        trigger_data = {
            "type": "motion",  # Default to motion
            "confidence": random.uniform(0.75, 0.95),
            "zone": random.choice(["center", "left", "right", "top", "bottom"]),
            "detection_class": "motion",
            "detection_details": None
        }
        
        # Generate ingestion method information
        ingestion_method = random.choice(INGESTION_METHODS)
        ingestion_data = {
            "method": ingestion_method,
            "source": {
                "email": None,
                "ftp": None,
                "manual": None,
                "api": None
            },
            "timestamp": upload_date.isoformat(),
            "batch_id": f"batch-{uuid.uuid4().hex[:8]}",
            "uploaded_by": "system",
            "processing_time_ms": random.randint(15, 120)
        }
        
        # Fill in source-specific fields
        if ingestion_method == "email":
            ingestion_data["source"]["email"] = {
                "from": f"{device_id}@camera.wisr.com",
                "message_id": f"<{uuid.uuid4().hex}.{uuid.uuid4().hex[:12]}@mx.example.com>",
                "sent_timestamp": (upload_date - timedelta(seconds=random.randint(3, 10))).isoformat(),
                "received_timestamp": upload_date.isoformat(),
                "subject": f"Motion Detected from {device_name} at {capture_date.strftime('%Y/%m/%d %H:%M:%S')}",
                "reception_delay_sec": random.randint(1, 10)
            }
        elif ingestion_method == "manual":
            ingestion_data["uploaded_by"] = f"user-{random.randint(100, 999)}"
        
        # Generate related media for videos (an image frame)
        related_media = []
        if media_type == "video":
            # 80% chance of having a related image
            if random.random() < 0.8:
                related_image_id = f"media-{uuid.uuid4().hex[:6]}"
                related_media.append({
                    "media_id": related_image_id,
                    "media_type": "image",
                    "relationship": "frame-of",
                    "capture_timestamp": capture_date.isoformat()
                })
        
        # Generate weather and astronomical data
        weather_data = self.generate_weather_data(capture_date)
        astronomical_data = self.generate_astronomical_data(capture_date, weather_data)
        
        # Get sun position for context
        sun_position = astronomical_data["sun"]["position"]
        
        # Generate enhanced detection data with multi-class support
        detection_data = self.generate_enhanced_detection_data(media_type, resolution_key, capture_date, sun_position)
        
        # Generate enrichment processes tracking
        enrichment_processes = self.generate_enrichment_processes(media_id, capture_date, detection_data)
        
        # Generate tags
        tags = self.generate_enhanced_tags(detection_data, weather_data, astronomical_data, media_type)
        
        # Generate user metadata
        user_metadata = self.generate_enhanced_user_metadata(detection_data, tags)
        
        # Generate access settings
        access_data = {
            "visibility": "private",
            "shared_with": [],
            "shared_links": [],
            "expires_timestamp": None
        }
        
        # Generate system metadata
        system_data = {
            "created_timestamp": upload_date.isoformat(),
            "created_by": "system",
            "updated_timestamp": processing_date.isoformat(),
            "updated_by": "system",
            "version": 1,
            "processing_status": "complete",
            "enrichment_status": {
                "weather": "success",
                "astronomical": "success",
                "detection": "success"
            }
        }
        
        # Add user updates if user metadata exists
        if user_metadata:
            system_data["updated_timestamp"] = user_metadata["last_viewed_timestamp"]
            system_data["updated_by"] = f"user-{random.randint(100, 999)}"
            system_data["version"] += 1
        
        # Create the complete media record
        media_record = {
            "@timestamp": capture_date.isoformat(),
            "tenant_id": tenant_id,
            "property": {
                "id": property_id,
                "name": property_name,
                "timezone": property_timezone
            },
            "media": {
                "id": media_id,
                "name": filename,
                "title": f"Motion Detection at {device_name}",
                "description": f"Detected: Motion from {device_name} at {capture_date.isoformat()}",
                "type": media_type,
                "capture_timestamp": capture_date.isoformat(),
                "capture_timestamp_local": capture_date_local,
                "upload_timestamp": upload_date.isoformat(),
                "upload_timestamp_local": upload_date.replace(tzinfo=None).isoformat() + "-05:00",
                "upload_delay_ms": int((upload_date - capture_date).total_seconds() * 1000),
                "status": "processed"
            },
            "file": file_data,
            "storage": storage_paths,
            "location": location,
            "device": device_data,
            "trigger": trigger_data,
            "ingestion": ingestion_data,
            "related": related_media,
            "weather": weather_data,
            "astronomical": astronomical_data,
            "detection": detection_data,
            "enrichment_processes": enrichment_processes,
            "user_metadata": user_metadata,
            "tags": tags,
            "access": access_data,
            "system": system_data
        }
        
        return media_record
    
    def generate_records_for_configuration(self):
        """Generate media records based on the configuration"""
        records = []
        record_index = 1
        
        # Get configuration parameters
        tenants = self.config.get("tenants", [])
        
        # Iterate through tenants, properties, and devices
        for tenant in tenants:
            tenant_id = tenant["id"]
            print(f"Generating records for tenant: {tenant_id}")
            
            for property_data in tenant.get("properties", []):
                property_id = property_data["id"]
                property_name = property_data["name"]
                print(f"  Property: {property_name} ({property_id})")
                
                for device in property_data.get("devices", []):
                    device_id = device["id"]
                    device_name = device["name"]
                    
                    # Get media count for this device
                    media_count = self.config.get("media_count_per_device", 10)
                    if isinstance(media_count, dict):
                        # If we have a range, use a random number in that range
                        if "min" in media_count and "max" in media_count:
                            media_count = random.randint(media_count["min"], media_count["max"])
                    
                    print(f"    Device: {device_name} ({device_id}) - Generating {media_count} records")
                    
                    # Generate records for this device
                    for i in range(media_count):
                        try:
                            record = self.generate_media_record(tenant, property_data, device, record_index)
                            records.append(record)
                            record_index += 1
                        except Exception as e:
                            error_traceback = traceback.format_exc()
                            print(f"Error generating record {i} for device {device_id}: {str(e)}")
                            print(f"Stack trace:\n{error_traceback}")     

        print(f"Generated {len(records)} total records")
        return records

    def generate_records(self, count=10):
        """Generate multiple random media records (legacy method)"""
        # If configuration has tenants, use that instead
        if self.config.get("tenants"):
            return self.generate_records_for_configuration()
        
        # Otherwise generate random records (for backward compatibility)
        records = []
        for i in range(count):
            records.append(self.generate_media_record({
                "id": "tenant-001",
                "name": "Default Tenant"
            }, {
                "id": "prop-123456",
                "name": "Default Property",
                "timezone": "America/Chicago"
            }, {
                "id": f"device-{i:03d}",
                "name": f"Camera {i}",
                "make": "Generic",
                "model": "Trail Camera",
                "serial_number": f"SN{random.randint(10000, 99999)}",
                "location": [-99.607781, 30.990075],
                "boundary_id": "bound-001"
            }, i + 1))
        return records
    
def load_config(config_file=None):
    """Load configuration from file or return default"""
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            try:
                config = yaml.safe_load(f)
                print(f"Loaded configuration from {config_file}")
                return config
            except Exception as e:
                print(f"Error loading configuration: {str(e)}")
                print("Using default configuration")
                return DEFAULT_CONFIG
    else:
        if config_file:
            print(f"Configuration file {config_file} not found")
            print("Using default configuration")
        return DEFAULT_CONFIG


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Generate random WISR media data and upload to Elasticsearch')
    parser.add_argument('--config', type=str, help='Path to configuration file (YAML)')
    parser.add_argument('--count', type=int, help='Number of records to generate (per device if using configuration)')
    parser.add_argument('--output', type=str, help='Output file for generated data (optional)')
    parser.add_argument('--endpoint', type=str, help='Elasticsearch endpoint URL')
    parser.add_argument('--api-key', type=str, help='Elasticsearch API key')
    parser.add_argument('--username', type=str, help='Elasticsearch username (if not using API key)')
    parser.add_argument('--password', type=str, help='Elasticsearch password (if not using API key)')
    parser.add_argument('--index-prefix', type=str, default='wisr-media', help='Elasticsearch index prefix (default: wisr-media)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for uploads (default: 100)')
    parser.add_argument('--no-verify', action='store_true', help='Disable SSL certificate verification')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode for detailed error information')
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override configuration with command line arguments
    if args.count:
        config["media_count_per_device"] = args.count
    
    if args.endpoint:
        config["elasticsearch"] = config.get("elasticsearch", {})
        config["elasticsearch"]["endpoint"] = args.endpoint
    
    if args.api_key:
        config["elasticsearch"] = config.get("elasticsearch", {})
        config["elasticsearch"]["api_key"] = args.api_key
        config["elasticsearch"]["use_api_key"] = True
    
    if args.username and args.password:
        config["elasticsearch"] = config.get("elasticsearch", {})
        config["elasticsearch"]["username"] = args.username
        config["elasticsearch"]["password"] = args.password
        config["elasticsearch"]["use_api_key"] = False
    
    if args.index_prefix:
        config["elasticsearch"] = config.get("elasticsearch", {})
        config["elasticsearch"]["index_prefix"] = args.index_prefix
    
    if args.no_verify:
        config["elasticsearch"] = config.get("elasticsearch", {})
        config["elasticsearch"]["verify_ssl"] = False
    
    # Create generator
    generator = MediaGenerator(config)
    
    # Generate records
    print("Generating media records...")
    records = generator.generate_records()
    print(f"Generated {len(records)} records successfully.")
    
    # Write to file if specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(records, f, indent=2)
        print(f"Saved records to {args.output}")
    
    # Upload to Elasticsearch if endpoint provided
    if "endpoint" in config.get("elasticsearch", {}):
        print(f"Uploading to Elasticsearch at {config['elasticsearch']['endpoint']}...")
        uploader = ElasticsearchUploader(config)
        
        # Check connection
        print("Checking Elasticsearch connection...")
        connection_ok, info = uploader.check_connection()
        if not connection_ok:
            print(f"Error connecting to Elasticsearch: {info}")
            sys.exit(1)
        
        print("Connected to Elasticsearch successfully.")
        
        # Upload data
        successful, errors = uploader.upload_records(records, args.batch_size)
        
        print(f"Upload complete. Successfully indexed {successful}/{len(records)} records.")
        
        if errors:
            print(f"Encountered {len(errors)} errors during upload.")
            if args.output or True:  # Always save errors if they occur
                error_file = args.output + "_errors.json" if args.output else "upload_errors.json"
                with open(error_file, 'w') as f:
                    json.dump(errors, f, indent=2)
                print(f"Saved error details to {error_file}")
                
                # Print the first few errors to help diagnose
                print("First few errors:")
                for i, error in enumerate(errors[:3]):
                    print(f"  Error {i+1}: {json.dumps(error)}")
    
    print("Done!")


if __name__ == "__main__":
    main()