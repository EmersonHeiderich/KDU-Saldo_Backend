saldo-api/
├── .env                 # Environment variables (SECRET_KEY, API creds, DB connection, etc.) # MODIFIED
├── .gitignore
├── requirements.txt     # MODIFIED (Added SQLAlchemy, psycopg)
├── run.py               # Simple script to run the Flask app
├── README.md            # Project overview, setup, structure # MODIFIED
│
└── src/
    ├── __init__.py
    ├── app.py               # Flask app factory (create_app) # MODIFIED (SQLAlchemy init)
    ├── config/
    │   ├── __init__.py
    │   ├── settings.py      # Load env vars, define Config object, build DB URI # MODIFIED
    │   └── README.md        # Explanation of config files # MODIFIED
    │
    ├── domain/              # Data models (DTOs for ERP and Local DB)
    │   ├── __init__.py
    │   ├── accounts_receivable.py
    │   ├── balance.py
    │   ├── cost.py
    │   ├── fabric_details.py
    │   ├── fiscal.py
    │   ├── observation.py
    │   ├── person.py
    │   ├── user.py
    │   └── README.md        # Explanation of domain models
    │
    ├── database/            # Database interaction layer (PostgreSQL with SQLAlchemy Core)
    │   ├── __init__.py      # Initialize SQLAlchemy engine, repositories, schema
    │   ├── base_repository.py # Uses SQLAlchemy Engine and text()
    │   ├── observation_repository.py # Adapted for SQLAlchemy
    │   ├── product_repository.py # Adapted for SQLAlchemy (Placeholder)
    │   ├── schema_manager.py # Handles table creation/migration (PostgreSQL syntax)
    │   ├── user_repository.py # Adapted for SQLAlchemy
    │   └── README.md        # Explanation of database layer
    │
    ├── services/            # Business logic layer
    │   ├── __init__.py
    │   ├── accounts_receivable_service.py
    │   ├── auth_service.py
    │   ├── customer_service.py
    │   ├── fabric_service.py
    │   ├── fiscal_service.py
    │   ├── observation_service.py
    │   ├── product_service.py
    │   └── README.md        # Explanation of business services
    │
    ├── erp_integration/     # Layer for interacting with the TOTVS ERP API
    │   ├── __init__.py
    │   ├── accounts_receivable_service.py
    │   ├── erp_auth_service.py
    │   ├── erp_balance_service.py
    │   ├── erp_cost_service.py
    │   ├── erp_fiscal_service.py
    │   ├── erp_person_service.py
    │   ├── erp_product_service.py
    │   └── README.md        # Explanation of ERP integration layer
    │
    ├── api/                 # Flask Blueprints and route definitions
    │   ├── __init__.py
    │   ├── routes/
    │   │   ├── __init__.py
    │   │   ├── accounts_receivable.py
    │   │   ├── auth.py
    │   │   ├── customer_panel.py
    │   │   ├── fabrics.py
    │   │   ├── fiscal.py
    │   │   ├── observations.py
    │   │   ├── products.py
    │   │   └── users.py
    │   ├── decorators.py
    │   ├── errors.py
    │   └── README.md        # Explanation of the API layer
    │
    └── utils/
        ├── __init__.py
        ├── fabric_list_builder.py
        ├── logger.py
        ├── matrix_builder.py
        ├── pdf_utils.py
        ├── system_monitor.py
        └── README.md        # Explanation of utility functions