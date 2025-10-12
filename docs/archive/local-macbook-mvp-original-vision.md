# 🚀 Local MacBook MVP: Hello Squad! App
## First WarmBoot with Max + Neo

---

## 🎯 **Mission: First AI Squad WarmBoot**

**Goal**: Demonstrate Max + Neo collaborating to build a simple "Hello, Squad!" web application
**Timeline**: 1-2 weeks
**Platform**: Local MacBook Pro M4 (24GB unified memory)
**Models**: Local Ollama models (Llama 3.1 8B + Qwen 2.5 7B)

---

## 📋 **Hello Squad! App PRD**

### **Product Overview**
A simple web application that demonstrates AI agent collaboration by displaying a welcome message and basic functionality.

### **Core Requirements**
1. **Welcome Page**: Display "Hello, Squad!" message
2. **Agent Status**: Show which agents built the app
3. **Simple Interaction**: Basic form with submit functionality
4. **Responsive Design**: Works on desktop and mobile
5. **Clean UI**: Modern, professional appearance

### **Technical Requirements**
- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Simple Python Flask API
- **Database**: SQLite for simplicity
- **Deployment**: Local development server
- **Version Control**: Git with clear commit history

### **Success Criteria**
- ✅ App loads and displays welcome message
- ✅ Form submission works correctly
- ✅ Responsive design implemented
- ✅ Clean, professional UI
- ✅ Git history shows agent collaboration

---

## 🛠️ **Implementation Steps**

### **Step 1: Local Model Setup (Day 1)**

#### **1.1 Install Ollama**
```bash
# Install Ollama
brew install ollama

# Start Ollama service
ollama serve

# Pull models in separate terminal
ollama pull llama3.1:8b    # For Max (Lead)
ollama pull qwen2.5:7b     # For Neo (Dev)
```

#### **1.2 Test Model Integration**
```bash
# Test Max's model
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "You are Max, a task lead. Create a simple project plan for a Hello Squad web app.",
  "stream": false
}'

# Test Neo's model  
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b", 
  "prompt": "You are Neo, a developer. Write a simple HTML page that says Hello Squad!",
  "stream": false
}'
```

### **Step 2: Agent Configuration (Day 2)**

#### **2.1 Update Base Agent for Local Models**
```python
# agents/base_agent.py
import requests
import json

class BaseAgent:
    def __init__(self, agent_id, role, model_name):
        self.agent_id = agent_id
        self.role = role
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
    
    def get_llm_response(self, prompt):
        """Get response from local Ollama model"""
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False
                }
            )
            return response.json()["response"]
        except Exception as e:
            return f"Error calling model: {str(e)}"
```

#### **2.2 Configure Max (Lead Agent)**
```python
# agents/roles/lead/agent.py
from base_agent import BaseAgent

class MaxAgent(BaseAgent):
    def __init__(self, identity="max"):
        super().__init__(identity, "lead", "llama3.1:8b")
        self.display_name = "Max"
    
    def create_project_plan(self, requirements):
        prompt = f"""
        You are Max, a task lead. Create a detailed project plan for this web application:
        
        Requirements: {requirements}
        
        Provide:
        1. Task breakdown
        2. Timeline estimates
        3. Technical approach
        4. Success criteria
        """
        return self.get_llm_response(prompt)
    
    def coordinate_team(self, task):
        prompt = f"""
        You are Max, coordinating the team. This task needs to be completed:
        
        Task: {task}
        
        Provide:
        1. Who should handle this task
        2. What information they need
        3. Expected deliverables
        4. Timeline
        """
        return self.get_llm_response(prompt)
```

#### **2.3 Configure Neo (Dev Agent)**
```python
# agents/roles/dev/agent.py
from base_agent import BaseAgent

class NeoAgent(BaseAgent):
    def __init__(self, identity="neo"):
        super().__init__(identity, "dev", "qwen2.5:7b")
        self.display_name = "Neo"
    
    def implement_feature(self, specification):
        prompt = f"""
        You are Neo, a developer. Implement this feature specification:
        
        Specification: {specification}
        
        Provide:
        1. Complete code implementation
        2. File structure
        3. Dependencies
        4. Testing approach
        """
        return self.get_llm_response(prompt)
    
    def review_code(self, code):
        prompt = f"""
        You are Neo, reviewing this code:
        
        Code: {code}
        
        Provide:
        1. Code quality assessment
        2. Potential improvements
        3. Security considerations
        4. Performance notes
        """
        return self.get_llm_response(prompt)
```

### **Step 3: WarmBoot Execution (Day 3-4)**

#### **3.1 Max Creates Project Plan**
```python
# warmboot_hello_squad.py
from agents.roles.lead.agent import MaxAgent
from agents.roles.dev.agent import NeoAgent

def run_hello_squad_warmboot():
    # Initialize agents
    max = MaxAgent()
    neo = NeoAgent()
    
    # Max creates project plan
    requirements = """
    Build a Hello Squad web application with:
    - Welcome page displaying "Hello, Squad!"
    - Agent status showing who built it
    - Simple form with submit functionality
    - Responsive design
    - Clean, professional UI
    """
    
    print("=== MAX CREATING PROJECT PLAN ===")
    project_plan = max.create_project_plan(requirements)
    print(project_plan)
    
    # Max coordinates with Neo
    print("\n=== MAX COORDINATING WITH NEO ===")
    coordination = max.coordinate_team("Implement the Hello Squad web application")
    print(coordination)
    
    # Neo implements the application
    print("\n=== NEO IMPLEMENTING APPLICATION ===")
    implementation = neo.implement_feature(requirements)
    print(implementation)
    
    return project_plan, coordination, implementation

if __name__ == "__main__":
    run_hello_squad_warmboot()
```

#### **3.2 Neo Implements the App**
```python
# Continue in warmboot_hello_squad.py
def neo_implement_app():
    neo = NeoAgent()
    
    # Neo creates the HTML structure
    html_spec = """
    Create a complete HTML page for Hello Squad app with:
    - Modern CSS styling
    - Responsive design
    - Form with name input and submit button
    - Display area for submitted names
    - Professional appearance
    """
    
    html_implementation = neo.implement_feature(html_spec)
    
    # Neo creates the Flask backend
    flask_spec = """
    Create a Flask backend for Hello Squad app with:
    - Route to serve the HTML page
    - Route to handle form submissions
    - SQLite database to store submissions
    - JSON API responses
    """
    
    flask_implementation = neo.implement_feature(flask_spec)
    
    return html_implementation, flask_implementation
```

### **Step 4: App Deployment & Testing (Day 5)**

#### **4.1 Create Project Structure**
```
hello_squad_app/
├── app.py                 # Flask backend
├── templates/
│   └── index.html        # HTML template
├── static/
│   └── style.css         # CSS styling
├── database.db           # SQLite database
└── requirements.txt      # Python dependencies
```

#### **4.2 Run the Application**
```bash
# Install dependencies
pip install flask

# Run the app
python app.py

# Test in browser
open http://localhost:5000
```

#### **4.3 Test Agent Collaboration**
```bash
# Run the WarmBoot
python warmboot_hello_squad.py

# Check git history
git log --oneline

# Verify app functionality
curl http://localhost:5000
```

---

## 🎯 **Success Metrics**

### **Technical Success**
- ✅ Ollama models running locally
- ✅ Max + Neo agents communicating
- ✅ Hello Squad app deployed and working
- ✅ Form submission functional
- ✅ Responsive design implemented

### **Collaboration Success**
- ✅ Max creates project plan
- ✅ Max coordinates with Neo
- ✅ Neo implements the application
- ✅ Clear task handoff between agents
- ✅ Git history shows collaboration

### **Performance Success**
- ✅ App loads in < 2 seconds
- ✅ Form submission works instantly
- ✅ No memory issues on M4 Pro
- ✅ Models respond in < 5 seconds

---

## 🚀 **Next Steps After Success**

### **Phase 2: Add EVE (QA)**
- Add EVE agent with Phi 3.5 Mini model
- Implement testing and validation
- Add quality gates to the process

### **Phase 3: Add Data (Analytics)**
- Add Data agent for progress tracking
- Implement metrics and reporting
- Add performance monitoring

### **Phase 4: Scale Up**
- Add more complex features
- Implement database integration
- Add user authentication

---

## 💡 **Key Benefits of Local Approach**

1. **Fast Iteration**: No network latency
2. **Cost Effective**: No API costs
3. **Privacy**: All data stays local
4. **Reliable**: No external dependencies
5. **Scalable**: Easy to add more agents

---

**This local MacBook MVP gets you to your first WarmBoot success quickly and cost-effectively!** 🚀
