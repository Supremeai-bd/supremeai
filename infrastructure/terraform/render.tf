terraform {
  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.3"
    }
  }
}

provider "render" {
  api_key = var.render_api_key
}

resource "render_web_service" "supremeai_render_node" {
  name    = "supremeai-backend-render"
  plan    = "free"
  region  = "oregon"
  runtime = "docker"

  # আপনার কোডবেস রিপোজিটরির ডিরেক্ট হুক
  repo    = "https://github.com/paykaribazaronline/supremeai"
  branch  = "main"

  env_vars = {
    "SUPREME_ENVIRONMENT" = "production"
  }
}
