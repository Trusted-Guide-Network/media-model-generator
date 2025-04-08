# main.tf
# Terraform configuration for WISR project Elasticsearch deployment

# Configure the Elastic Cloud provider
terraform {
  required_providers {
    ec = {
      source  = "elastic/ec"
      version = "0.12.2"
    }
    elasticstack = {
      source  = "elastic/elasticstack"
      version = "0.11.14"
    }
  }
}


# for inital testing only.  Needs to be stored elsewhere like $ export EC_API_KEY="<apikey value>"
provider "ec" {
  apikey = ""
}

# Variables
variable "deployment_name" {
  description = "Name for the Elastic Cloud Project"
  type        = string
  default     = "media-model-generator"
}

variable "region" {
  description = "Elastic Cloud region"
  type        = string
  default     = "us-east-1"
}


# Create an Elastic Cloud deployment
resource "ec_observability_project" "ec_serverless" {
  name      = var.deployment_name
  alias      = var.deployment_name
  region_id = var.region
}

# Load JSON files - using the exact file names from your system
data "local_file" "wisr_media_fields" {
  filename = "${path.module}/config/wisr-media-index-template.json"
}

locals {
  # Decode JSON files once
  wisr_media_field_json = jsondecode(data.local_file.wisr_media_fields.content)
}


# Configure the Elastic Stack provider
provider "elasticstack" {
  elasticsearch {
    endpoints = [ec_observability_project.ec_serverless.endpoints.elasticsearch]
    username  = ec_observability_project.ec_serverless.credentials.username
    password  = ec_observability_project.ec_serverless.credentials.password
  }
  kibana {
    endpoints = [ec_observability_project.ec_serverless.endpoints.kibana]
    username  = ec_observability_project.ec_serverless.credentials.username
    password  = ec_observability_project.ec_serverless.credentials.password
  }
  fleet {}
}

# Load index template from file
resource "elasticstack_elasticsearch_index_template" "wisr_media_template" {
    name           = "wisr-media-template"
    index_patterns = ["wisr-media-*"]

    data_stream {}

    template {
        mappings = jsonencode(lookup(try(local.wisr_media_field_json.template, {}), "mappings", {}))
        settings = jsonencode(lookup(try(local.wisr_media_field_json.template, {}), "settings", {}))
    }
}


# Create a Kibana data view
resource "elasticstack_kibana_data_view" "wisr_media_data_view" {
  data_view = {
    id              = "wisr-media-*"
    name            = "WISR Media"
    title           = "wisr-media-*"
    time_field_name = "@timestamp"
  }
}

# Read-only API key for data retrieval
resource "elasticstack_elasticsearch_security_api_key" "wisr_media_readonly_api_key" {
  name = "wisr-media-readonly-api-key"
  role_descriptors = jsonencode({
    wisr_media_read = {
      cluster = ["monitor"],
      indices = [{
        names = ["wisr-media-*"],
        # privileges = ["read", "view_index_metadata", "read_cross_cluster"] # read_cross_cluster is not supported in serverless
        privileges = ["read", "view_index_metadata"]
        allow_restricted_indices = false

      }]
    }
  })
}

# Create an API key for data ingestion
resource "elasticstack_elasticsearch_security_api_key" "wisr_media_ingestion_api_key" {
  name = "wisr-media-ingestion-api-key"
  role_descriptors = jsonencode({
    wisr_media_ingest = {
      cluster = ["monitor"],
      indices = [{
        names      = ["wisr-media-*"],
        privileges = ["create_index", "create_doc", "index", "write", "view_index_metadata"]
        allow_restricted_indices = false
      }]
    }
  })
}

# Outputs
output "elasticsearch_endpoint" {
  value = ec_observability_project.ec_serverless.endpoints.elasticsearch
}

output "elasticsearch_cloudid"{
  value = ec_observability_project.ec_serverless.cloud_id
}

output "kibana_endpoint" {
  value = ec_observability_project.ec_serverless.endpoints.kibana
}

output "integrations_server_endpoint" {
  value = ec_observability_project.ec_serverless.endpoints.apm
}

output "elasticsearch_username" {
  value     = ec_observability_project.ec_serverless.credentials.username
  sensitive = false
}

output "elasticsearch_password" {
  value     = ec_observability_project.ec_serverless.credentials.password
  sensitive = true
}

output "wisr_media_readonly_api_key" {
  value     = elasticstack_elasticsearch_security_api_key.wisr_media_readonly_api_key
  sensitive = true
}
output "wisr_media_readonly_api_key_encoded" {
  value     = elasticstack_elasticsearch_security_api_key.wisr_media_readonly_api_key.encoded
  sensitive = true
}

output "sigint-email-indexing-api-key" {
  value     = elasticstack_elasticsearch_security_api_key.wisr_media_ingestion_api_key
  sensitive = true
}
output "media_ingestion_api_key_encoded" {
  value     = elasticstack_elasticsearch_security_api_key.wisr_media_ingestion_api_key.encoded
  sensitive = true
}