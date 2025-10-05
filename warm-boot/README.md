# WarmBoot Applications

This directory contains applications built by SquadOps agent collaboration through the WarmBoot process.

## Structure

```
warm-boot/
├── apps/                    # Applications built by agents
│   └── hello-squad/        # Hello Squad web application
│       ├── Dockerfile      # Container definition
│       ├── package.json    # Node.js dependencies
│       ├── server/         # Express.js backend
│       └── public/         # Frontend web interface
├── runs/                    # WarmBoot run history and logs
│   └── run-001/            # First successful WarmBoot run
│       ├── run-001-summary.md
│       ├── run-001-logs.json
│       └── release_manifest.yaml
└── README.md              # This file

## Documentation Structure

WarmBoot runs are documented across multiple directories:

- **Framework Documentation**: `docs/framework/` - How SquadOps works
- **Application Documentation**: `docs/prd/` - Product requirements
- **Test Documentation**: `testing/test_cases/` - Test specifications
- **Run History**: `warm-boot/runs/` - Execution logs and summaries
```

## Hello Squad Application

**Built by:** Max (LeadAgent) + Neo (DevAgent)  
**Technology:** Vue.js 3 + Express.js + WebSocket  
**Status:** ✅ Running at http://localhost:3000  
**WarmBoot Date:** 2025-10-05  

### Features
- Welcome page with agent credits
- Real-time name submission form
- WebSocket-powered live updates
- Modern responsive design
- REST API endpoints

### Access
- **Web Interface:** http://localhost:3000
- **API Status:** http://localhost:3000/api/status
- **API Names:** http://localhost:3000/api/names

## WarmBoot Process

1. **Max (LeadAgent)** creates project plan using Llama 3.1 8B
2. **Max** delegates specific tasks to Neo via RabbitMQ
3. **Neo (DevAgent)** implements features using Qwen 2.5 7B
4. **SquadOps Protocol** deploys application as Docker container
5. **Application** becomes accessible in SquadOps infrastructure

This demonstrates complete end-to-end agent collaboration from planning to deployment.
