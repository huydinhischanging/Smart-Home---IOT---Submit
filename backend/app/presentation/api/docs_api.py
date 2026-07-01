# app/presentation/api/docs_api.py
"""
Swagger UI endpoint — phục vụ tài liệu API tự động.
Truy cập: http://127.0.0.1:5000/api/docs
"""

import os
from flask import Blueprint, render_template_string, send_file, jsonify

docs_api = Blueprint("docs_api", __name__)

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Alfred API Docs — IOT Smart Home for Elderly</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
  <style>
    body { margin: 0; background: #0a0e1a; }
    .swagger-ui .topbar { background: #111827; }
    .swagger-ui .topbar .download-url-wrapper .select-label select { border: 1px solid #fbbf24; }
    .swagger-ui .info .title { color: #fbbf24; }
    .swagger-ui .info { background: #0d1117; padding: 16px; border-radius: 8px; }
    #swagger-ui { max-width: 1200px; margin: 0 auto; padding: 0 16px 40px; }
    .topbar-wrapper img { display: none; }
    .topbar-wrapper::before {
      content: "⚡ Alfred API — IOT Smart Home";
      color: #fbbf24;
      font-weight: 700;
      font-size: 18px;
      padding: 0 8px;
    }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/api/docs/openapi.yaml",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
      displayRequestDuration: true,
      tryItOutEnabled: true,
      requestCredentials: "include",
    });
  </script>
</body>
</html>
"""


@docs_api.route("/api/docs", methods=["GET"])
def swagger_ui():
    """Swagger UI HTML — truy cập /api/docs để xem tài liệu API"""
    return render_template_string(_SWAGGER_HTML)


@docs_api.route("/api/docs/openapi.yaml", methods=["GET"])
def openapi_spec():
    """Phục vụ file OpenAPI spec YAML"""
    spec_path = os.path.join(
        os.path.dirname(__file__),         # presentation/api/
        "..", "..",                         # app/
        "..",                               # backend/
        "static", "openapi.yaml",
    )
    spec_path = os.path.normpath(spec_path)
    if not os.path.isfile(spec_path):
        return jsonify({"error": "openapi.yaml not found"}), 404
    return send_file(spec_path, mimetype="text/yaml")
