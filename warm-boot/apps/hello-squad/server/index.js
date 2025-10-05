const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const cors = require('cors');
const path = require('path');

const app = express();
const server = http.createServer(app);

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// Initialize WebSocket server
const wss = new WebSocket.Server({ server });

// Store for names (in production, use a database)
let names = [];

wss.on('connection', (ws) => {
  console.log('Client connected to Hello Squad');

  // Send current names to new client
  ws.send(JSON.stringify({ 
    action: 'init', 
    names: names 
  }));

  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      
      if (data.action === 'add-name') {
        const name = data.name.trim();
        if (name && !names.includes(name)) {
          names.push(name);
          
          // Broadcast to all clients
          wss.clients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
              client.send(JSON.stringify({ 
                action: 'name-added', 
                name: name,
                names: names 
              }));
            }
          });
        }
      }
    } catch (error) {
      console.error('WebSocket message error:', error);
    }
  });

  ws.on('close', () => {
    console.log('Client disconnected from Hello Squad');
  });
});

// API Routes
app.post('/api/names', (req, res) => {
  const { name } = req.body;
  const trimmedName = name?.trim();
  
  if (!trimmedName) {
    return res.status(400).json({ error: 'Name is required' });
  }
  
  if (!names.includes(trimmedName)) {
    names.push(trimmedName);
  }
  
  res.status(201).json({ 
    message: 'Name added successfully',
    name: trimmedName,
    names: names 
  });
});

app.get('/api/names', (req, res) => {
  res.status(200).json({ names: names });
});

app.get('/api/status', (req, res) => {
  res.status(200).json({ 
    status: 'Hello Squad is running!',
    agents: ['Max (LeadAgent)', 'Neo (DevAgent)'],
    names_count: names.length,
    timestamp: new Date().toISOString()
  });
});

// Version endpoint for run-002 enhancement
app.get('/api/version', (req, res) => {
  res.status(200).json({
    version: process.env.APP_VERSION || '1.1.0',
    run_id: process.env.WARMBOOT_RUN_ID || 'run-002',
    timestamp: process.env.BUILD_TIMESTAMP || new Date().toISOString(),
    git_hash: process.env.GIT_HASH || 'unknown'
  });
});

// Serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Hello Squad server running on port ${PORT}`);
  console.log(`📱 Access at: http://localhost:${PORT}`);
  console.log(`🤖 Built by: Max & Neo (SquadOps Agents)`);
});
