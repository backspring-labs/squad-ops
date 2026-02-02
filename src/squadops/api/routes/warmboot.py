"""
WarmBoot form and submission routes.

Part of SIP-0.8.9 Health Check refactor.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from squadops.api.health_app import HealthChecker

router = APIRouter(prefix="/warmboot", tags=["warmboot"])
logger = logging.getLogger(__name__)

# Will be injected at startup
_health_checker: "HealthChecker | None" = None


def init_routes(health_checker: "HealthChecker") -> None:
    """Initialize routes with dependencies."""
    global _health_checker
    _health_checker = health_checker


class WarmBootRequest(BaseModel):
    """WarmBoot submission request."""

    run_id: str
    application: str
    request_type: str
    agents: list[str]
    priority: str
    description: str
    requirements: str | None = None
    prd_path: str | None = None
    requirements_text: str | None = None


@router.post("/submit")
async def submit_warmboot(request: WarmBootRequest):
    """Submit a WarmBoot request to agents"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    result = await _health_checker.submit_warmboot_request(request)
    return JSONResponse(content=result)


@router.get("/status/{run_id}")
async def get_warmboot_status(run_id: str):
    """Get status of a WarmBoot request"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    result = await _health_checker.get_warmboot_status(run_id)
    return JSONResponse(content=result)


@router.get("/prds")
async def get_available_prds():
    """Get available PRDs from warm-boot/prd/ directory"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    prds = await _health_checker.get_available_prds()
    return JSONResponse(content=prds)


@router.get("/next-run-id")
async def get_next_run_id():
    """Get next sequential run ID"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    run_id = await _health_checker.get_next_run_id()
    return JSONResponse(content={"run_id": run_id})


@router.get("/agents")
async def get_agent_status_for_form():
    """Get agent status for form checkbox defaults"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    agents = await _health_checker.get_agent_status()
    return JSONResponse(content=agents)


@router.get("/messages")
async def get_agent_messages(since: str | None = None):
    """Get recent agent messages for live communication feed"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    messages = await _health_checker.get_agent_messages(since)
    return JSONResponse(content=messages)


@router.get("/form")
async def warmboot_form():
    """Get WarmBoot request form HTML"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    # Load instances for dynamic agent list
    instances = _health_checker._load_instances()

    # Build agent checkboxes dynamically
    agent_checkboxes_html = []
    agents_list = list(instances.items())

    # Group agents into rows of 3
    for i in range(0, len(agents_list), 3):
        row_agents = agents_list[i : i + 3]
        row_class = "row mt-2" if i > 0 else "row"
        row_html = f'                        <div class="{row_class}">\n'
        for agent_id, instance_info in row_agents:
            display_name = instance_info["display_name"]
            role = instance_info["role"]
            # Check max and neo by default
            checked = "checked" if agent_id in ["max", "neo"] else ""
            row_html += f'''                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_{agent_id}" name="agents" value="{agent_id}" {checked}>
                                    <label class="form-check-label" for="agent_{agent_id}">{display_name} ({role.title()})</label>
                                </div>
                            </div>
'''
        row_html += "                        </div>"
        agent_checkboxes_html.append(row_html)

    agents_section = "\n".join(agent_checkboxes_html)

    html_content = (
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SquadOps WarmBoot Request</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            .form-container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .status-container {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            .status-success {
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            .status-error {
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="form-container">
                <h1 class="mb-4">SquadOps WarmBoot Request</h1>
                <p class="text-muted">Submit a WarmBoot request directly to agents - no AI scripting, real agent communication only.</p>

                <form id="warmbootForm">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="run_id" class="form-label">Run ID</label>
                                <input type="text" class="form-control" id="run_id" name="run_id" required>
                                <div class="form-text">e.g., run-007, feature-auth, bug-fix-001</div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="application" class="form-label">Application</label>
                                <select class="form-select" id="application" name="application" required>
                                    <option value="">Select Application</option>
                                    <option value="HelloSquad">HelloSquad</option>
                                    <option value="SquadOps-Framework">SquadOps Framework</option>
                                    <option value="Health-Check">Health Check Service</option>
                                    <option value="Custom">Custom Application</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="request_type" class="form-label">Request Type</label>
                                <select class="form-select" id="request_type" name="request_type" required>
                                    <option value="">Select Type</option>
                                    <option value="from-scratch">From-Scratch Build (archive previous, build new)</option>
                                    <option value="feature-update">Feature Update (modify existing)</option>
                                    <option value="bug-fix">Bug Fix (fix existing)</option>
                                    <option value="refactor">Refactor (improve existing)</option>
                                    <option value="deployment">Deployment (deploy existing)</option>
                                    <option value="testing">Testing (test existing)</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="priority" class="form-label">Priority</label>
                                <select class="form-select" id="priority" name="priority" required>
                                    <option value="">Select Priority</option>
                                    <option value="HIGH">High</option>
                                    <option value="MEDIUM">Medium</option>
                                    <option value="LOW">Low</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="agents" class="form-label">Agents</label>
                        <div class="row">
"""
        + agents_section
        + """
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="description" class="form-label">Description</label>
                        <textarea class="form-control" id="description" name="description" rows="4" required placeholder="Describe what you want the agents to build or accomplish..."></textarea>
                    </div>

                    <div class="mb-3">
                        <label for="requirements" class="form-label">Requirements (Optional)</label>
                        <textarea class="form-control" id="requirements" name="requirements" rows="3" placeholder="Additional technical requirements, constraints, or specifications..."></textarea>
                    </div>

                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg">Submit WarmBoot Request</button>
                        <a href="/health" class="btn btn-secondary">Back to Health Dashboard</a>
                    </div>
                </form>

                <div class="mt-4">
                    <h4>Live Agent Communication</h4>
                    <div class="agent-chat-container">
                        <textarea id="agentChat" class="form-control" rows="15" readonly
                                  style="font-family: monospace; font-size: 12px; background-color: #f8f9fa;"
                                  placeholder="Agent communication will appear here after submitting a WarmBoot request..."></textarea>
                        <div class="chat-controls mt-2">
                            <button id="clearChat" class="btn btn-sm btn-outline-secondary">Clear</button>
                            <span id="chatStatus" class="badge bg-secondary ms-2">Waiting</span>
                        </div>
                    </div>
                </div>

                <div id="statusContainer" class="status-container">
                    <div id="statusMessage"></div>
                    <div id="statusDetails" class="mt-2"></div>
                </div>
            </div>
        </div>

        <script>
            let currentRunId = null;
            let chatRefreshInterval = null;
            let lastMessageTime = null;

            // Initialize form on page load
            document.addEventListener('DOMContentLoaded', async function() {
                await initializeForm();
            });

            async function initializeForm() {
                // Generate Run ID
                await generateRunId();

                // Populate PRD dropdown
                await populatePrdDropdown();

                // Set up agent checkboxes
                await setupAgentCheckboxes();

                // Set up chat controls
                setupChatControls();
            }

            async function generateRunId() {
                try {
                    const response = await fetch('/warmboot/next-run-id');
                    const result = await response.json();
                    document.getElementById('run_id').value = result.run_id;
                    currentRunId = result.run_id;
                } catch (error) {
                    console.error('Failed to generate Run ID:', error);
                    document.getElementById('run_id').value = 'run-001';
                    currentRunId = 'run-001';
                }
            }

            async function populatePrdDropdown() {
                try {
                    const response = await fetch('/warmboot/prds');
                    const prds = await response.json();
                    const prdSelect = document.getElementById('application');

                    // Clear existing options except the first one
                    prdSelect.innerHTML = '<option value="">Select Application</option>';

                    // Add PRD options
                    prds.forEach(prd => {
                        const option = document.createElement('option');
                        option.value = prd.file_path;
                        option.textContent = `${prd.title} (${prd.pid})`;
                        option.title = prd.description;
                        prdSelect.appendChild(option);
                    });

                    // Add custom options
                    const customOption = document.createElement('option');
                    customOption.value = 'custom';
                    customOption.textContent = 'Custom Application';
                    prdSelect.appendChild(customOption);

                } catch (error) {
                    console.error('Failed to load PRDs:', error);
                }
            }

            async function setupAgentCheckboxes() {
                try {
                    const response = await fetch('/warmboot/agents');
                    const agents = await response.json();

                    agents.forEach(agent => {
                        const checkbox = document.getElementById(`agent_${agent.agent.toLowerCase()}`);
                        if (checkbox) {
                            // Set default selection based on agent status
                            const onlineStatuses = ['online', 'available', 'active-non-blocking'];
                            checkbox.checked = onlineStatuses.includes(agent.status);
                        }
                    });
                } catch (error) {
                    console.error('Failed to load agent status:', error);
                }
            }

            function setupChatControls() {
                // Clear chat button
                document.getElementById('clearChat').addEventListener('click', function() {
                    document.getElementById('agentChat').value = '';
                    lastMessageTime = null;
                });
            }

            function startChatFeed() {
                if (chatRefreshInterval) {
                    clearInterval(chatRefreshInterval);
                }

                const chatStatus = document.getElementById('chatStatus');
                chatStatus.className = 'badge bg-success ms-2';
                chatStatus.textContent = 'Live';

                chatRefreshInterval = setInterval(async () => {
                    try {
                        const sinceParam = lastMessageTime ? `?since=${lastMessageTime}` : '';
                        const response = await fetch(`/warmboot/messages${sinceParam}`);
                        const messages = await response.json();

                        if (messages.length > 0) {
                            const chatArea = document.getElementById('agentChat');

                            messages.forEach(msg => {
                                const formattedMsg = formatMessage(msg);
                                chatArea.value += formattedMsg + '\\n';
                            });

                            // Auto-scroll to bottom
                            chatArea.scrollTop = chatArea.scrollHeight;

                            // Update last message time
                            lastMessageTime = messages[messages.length - 1].timestamp;
                        }
                    } catch (error) {
                        console.error('Chat feed error:', error);
                    }
                }, 1000); // Refresh every second
            }

            function formatMessage(msg) {
                const timestamp = new Date(msg.timestamp).toLocaleTimeString();
                const icon = getMessageIcon(msg.message_type);
                const direction = msg.sender === 'warmboot-orchestrator' ? '<-' : '->';

                return `[${timestamp}] ${icon} ${msg.message_type}: ${msg.recipient} ${direction} ${msg.sender}\\n           "${msg.content}"`;
            }

            function getMessageIcon(messageType) {
                const icons = {
                    'WARMBOOT_REQUEST': '[BOOT]',
                    'TASK_ASSIGNMENT': '[TASK]',
                    'TASK_ACKNOWLEDGED': '[ACK]',
                    'TASK_UPDATE': '[UPD]',
                    'PROGRESS_UPDATE': '[PROG]',
                    'BUILD_START': '[BUILD]',
                    'TASK_COMPLETED': '[DONE]',
                    'TASK_FAILED': '[FAIL]'
                };
                return icons[messageType] || '[MSG]';
            }

            // Form submission
            document.getElementById('warmbootForm').addEventListener('submit', async function(e) {
                e.preventDefault();

                const formData = new FormData(e.target);
                const agents = Array.from(document.querySelectorAll('input[name="agents"]:checked')).map(cb => cb.value);

                const requestData = {
                    run_id: formData.get('run_id'),
                    application: formData.get('application'),
                    request_type: formData.get('request_type'),
                    agents: agents,
                    priority: formData.get('priority'),
                    description: formData.get('description'),
                    requirements: formData.get('requirements') || null
                };

                try {
                    const response = await fetch('/warmboot/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(requestData)
                    });

                    const result = await response.json();

                    const statusContainer = document.getElementById('statusContainer');
                    const statusMessage = document.getElementById('statusMessage');
                    const statusDetails = document.getElementById('statusDetails');

                    if (result.status === 'success') {
                        statusContainer.className = 'status-container status-success';
                        statusMessage.innerHTML = '<strong>Success!</strong> ' + result.message;
                        statusDetails.innerHTML = `
                            <strong>Run ID:</strong> ${result.run_id}<br>
                            <strong>Agents Notified:</strong> ${result.agents_notified.join(', ')}<br>
                            <strong>Timestamp:</strong> ${result.timestamp}<br>
                            <a href="/warmboot/status/${requestData.run_id}" class="btn btn-sm btn-outline-success mt-2">View Status</a>
                        `;

                        // Start live chat feed
                        startChatFeed();

                    } else {
                        statusContainer.className = 'status-container status-error';
                        statusMessage.innerHTML = '<strong>Error!</strong> ' + result.message;
                        statusDetails.innerHTML = `<strong>Timestamp:</strong> ${result.timestamp}`;
                    }

                    statusContainer.style.display = 'block';
                    statusContainer.scrollIntoView({ behavior: 'smooth' });

                } catch (error) {
                    const statusContainer = document.getElementById('statusContainer');
                    const statusMessage = document.getElementById('statusMessage');

                    statusContainer.className = 'status-container status-error';
                    statusMessage.innerHTML = '<strong>Network Error!</strong> ' + error.message;
                    statusContainer.style.display = 'block';
                    statusContainer.scrollIntoView({ behavior: 'smooth' });
                }
            });
        </script>
    </body>
    </html>
    """
    )
    return HTMLResponse(content=html_content)
