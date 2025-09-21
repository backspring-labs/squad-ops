#!/usr/bin/env python3
"""
Test script to send a task to Max agent
"""

import asyncio
import aio_pika
import json
from datetime import datetime

async def send_task_to_max():
    """Send a test task to Max agent"""
    
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust("amqp://squadops:squadops123@localhost:5672/")
    channel = await connection.channel()
    
    # Declare the queue (in case it doesn't exist)
    queue = await channel.declare_queue("max_tasks", durable=True)
    
    # Create a test task
    test_task = {
        "task_id": f"test_task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "type": "governance",
        "description": "Test task for Max - review project requirements",
        "priority": "medium",
        "tags": ["test", "governance"],
        "payload": {
            "project_name": "HelloSquad",
            "requirements": ["User authentication", "Basic CRUD operations"],
            "deadline": "2024-12-31"
        }
    }
    
    # Send the task
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(test_task).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        ),
        routing_key="max_tasks"
    )
    
    print(f"✅ Sent test task to Max: {test_task['task_id']}")
    print(f"Task details: {test_task['description']}")
    
    await connection.close()

if __name__ == "__main__":
    asyncio.run(send_task_to_max())
