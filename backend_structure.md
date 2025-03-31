saldo-api/
├── .env                 # Environment variables (SECRET_KEY, API creds, DB path, etc.)
├── .gitignore
├── requirements.txt
├── run.py               # Simple script to run the Flask app
├── README.md            # Project overview, setup, structure
│
└── src/
    ├── __init__.py
    ├── app.py               # Flask app factory (create_app)
    ├── config/
    │   ├── __init__.py
    │   ├── settings.py      # Load env vars, define Config object
    │   └── README.md        # Explanation of config files
    │
    ├── domain/              # Data models (formerly models)
    │   ├── __init__.py
    │   ├── accounts_receivable.py # <<< ADDED
    │   ├── balance.py       # Balance, ProductItem, ProductResponse
    │   ├── cost.py          # Cost, ProductCost, CostResponse
    │   ├── fabric_details.py# TecidoDetalhes (renamed from product_model.py)
    │   ├── fiscal.py        # <<< (Este foi adicionado anteriormente)
    │   ├── observation.py   # Observation data model (if needed, or use dict)
    │   ├── person.py        # Address, Phone, Email, IndividualDataModel, etc.
    │   ├── user.py          # User, UserPermissions
    │   └── README.md        # Explanation of domain models
    │
    ├── database/            # Database interaction layer (formerly db)
    │   ├── __init__.py      # Initialize pool, repositories, schema
    │   ├── base_repository.py
    │   ├── connection_pool.py
    │   ├── observation_repository.py # Specific repo for observations
    │   ├── product_repository.py # Placeholder
    │   ├── schema_manager.py # Handles table creation/migration
    │   ├── user_repository.py
    │   └── README.md        # Explanation of database layer
    │
    ├── services/            # Business logic layer
    │   ├── __init__.py
    │   ├── accounts_receivable_service.py # <<< ADDED
    │   ├── auth_service.py    # User authentication/authorization logic
    │   ├── customer_service.py# Logic related to customer panel (using ERP data)
    │   ├── fabric_service.py  # Logic for fabric list building/filtering
    │   ├── fiscal_service.py  # <<< (Este foi adicionado anteriormente)
    │   ├── observation_service.py # Business logic for observations
    │   ├── product_service.py # Logic for product matrix building
    │   └── README.md        # Explanation of business services
    │
    ├── erp_integration/     # Layer for interacting with the TOTVS ERP API
    │   ├── __init__.py
    │   ├── accounts_receivable_service.py # <<< ADDED
    │   ├── erp_auth_service.py # Handles ERP API authentication (Bearer token)
    │   ├── erp_balance_service.py # Fetches balance data from ERP
    │   ├── erp_cost_service.py    # Fetches cost data from ERP
    │   ├── erp_fiscal_service.py # <<< (Este foi adicionado anteriormente)
    │   ├── erp_person_service.py  # Fetches person data from ERP
    │   ├── erp_product_service.py # Fetches product details (like fabric details) from ERP
    │   └── README.md        # Explanation of ERP integration layer
    │
    ├── api/                 # Flask Blueprints and route definitions
    │   ├── __init__.py      # Register all blueprints
    │   ├── routes/
    │   │   ├── __init__.py
    │   │   ├── accounts_receivable.py # <<< ADDED
    │   │   ├── auth.py          # /api/auth/* endpoints
    │   │   ├── customer_panel.py# /api/customer_panel/* endpoints
    │   │   ├── fabrics.py       # /api/fabrics/* endpoints
    │   │   ├── fiscal.py        # <<< (Este foi adicionado anteriormente)
    │   │   ├── observations.py  # /api/observations/*
    │   │   ├── products.py      # /api/products/* endpoints
    │   │   └── users.py         # /api/users/* endpoints
    │   ├── decorators.py    # Authorization decorators
    │   ├── errors.py        # Custom error handlers and exceptions
    │   └── README.md        # Explanation of the API layer
    │
    └── utils/
        ├── __init__.py
        ├── fabric_list_builder.py # Helper to build fabric list structure
        ├── logger.py          # Logging setup
        ├── matrix_builder.py  # Helper to build product matrix structure
        ├── pdf_utils.py       # <<< ADDED
        ├── system_monitor.py  # <<< (Este foi adicionado anteriormente)
        └── README.md        # Explanation of utility functions