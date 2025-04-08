# Media Model Data Generator

Generates random sample data matching the WISR Media data model and uploads to Elasticsearch
This version includes support for:
- Multiple tenants
- Multiple properties per tenant
- Multiple devices per property
- Configurable number of media items per device
- Enhanced object detection with wildlife, people, and vehicles
- Enrichment process tracking


This repository provides two components designed to help test the WISR proposed data model:
1. Simple terraform stack to spin up and configure an Elastic Cloud Serverless Project to ingest the sample data
2. A simple python script that generates sample data for the WISR Platform.
   - Curently only generates the final data output which is stored in Elastic.  It does not create images or exercise the ingestion pipeline

Requirements:
- Python >= 3.9
- Terraform
- API Key for Elastic Cloud that allows you to perform CRUD based operations


## How to use
1.  Clone this repoistory from GitHub to you local system
2.  Install python dependencies:  ip install elasticsearch pyyaml requests
3.  Change directories to the terraform directory
4.  Run terraform init
5.  Run terraform apply
6.  Run the script with various options
    - Sample config files are provided  

### Generate and upload data with a configuration file
python data_generator.py --config example-config.yaml --endpoint https://your-elasticsearch-endpoint:9243 --api-key YOUR_API_KEY

### Just generate data without uploading
python data_generator.py --config example-config.yaml --output test_data.json

### Generate a specific number of records per device
python data_generator.py --config example-config.yaml --count 20 --output test_data.json
