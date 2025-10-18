# 📄 Product Requirements Document — HelloSquad Simple (PID-001)

## 1. Executive Summary

### About SquadOps
**SquadOps** is an AI agent orchestration framework that enables autonomous software development through specialized AI agents working together. The framework includes agents like Max (Lead Agent), Neo (Developer Agent), EVE (QA Agent), and others, each with specific roles and capabilities. SquadOps uses real LLM integration (Ollama), containerized deployment, event-driven communication (RabbitMQ), and comprehensive telemetry to enable AI agents to build, test, and deploy applications autonomously.

### HelloSquad Application
**HelloSquad** is a simple web application that demonstrates the SquadOps framework's ability to generate and deploy real applications using AI agents.

**Problem**: Need a simple demonstration of AI agent collaboration.

**Solution**: A basic web application that shows "Hello SquadOps" with version information and real system data.

---

## 2. Functional Requirements

### Core Features
1. **Welcome Message**
   - Display "Hello SquadOps" prominently
   - Show application version and build information
   - Clean, professional appearance

2. **Build Information**
   - Display WarmBoot run ID
   - Show build timestamp
   - Indicate which agents built the application

3. **Real System Data**
   - Show actual agent status (online/offline) from health system
   - Display basic infrastructure status
   - Show recent WarmBoot activity

4. **Framework Transparency**
   - Display SquadOps framework version
   - Show agent versions
   - Indicate when the application was built

### Success Criteria
- Application loads and displays correctly
- Shows real version and build information
- Displays actual system data (not simulated)
- Clean, professional appearance
- No errors or broken functionality

---

## 3. Technical Requirements

### Performance
- Page loads quickly (< 2 seconds)
- Responsive design (works on mobile and desktop)
- Works in all modern browsers

### Deployment
- Deploy to port 8080
- Serve from `/hello-squad/` path
- Containerized with nginx

### Data Sources
- **Agent Status**: GET http://localhost:8080/agents/status
- **Health Check**: GET http://localhost:8080/health  
- **Framework Version**: Available in environment as `SQUADOPS_VERSION`
- **Agent Versions**: Available in environment as `AGENT_VERSIONS`
- **Build Information**: Use WarmBoot run ID and build timestamp from environment
- **System Status**: GET http://localhost:8080/system/status

### Environment Variables Available
- `SQUADOPS_VERSION`: Framework version (e.g., "0.2.0")
- `AGENT_VERSIONS`: JSON object with agent versions
- `WARM_BOOT_SEQUENCE`: Current WarmBoot run ID (e.g., "068")
- `BUILD_TIMESTAMP`: When the application was built
- `HEALTH_API_URL`: Base URL for health check APIs (default: "http://localhost:8080")

---

## 4. Design Guidelines

### Visual Style
- Modern, clean design
- Professional color scheme
- Clear typography
- Simple layout with good spacing

### Content Structure
- Header with welcome message
- Main content area with build info
- System status section
- Footer with framework information

---

**Note**: This is a simple demonstration application. Keep it basic, functional, and focused on showing real data from the SquadOps system.