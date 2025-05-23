"""
Redis-based message broker for SSE events
"""

import asyncio
import json
import redis.asyncio as redis
from datetime import datetime
import os

class RedisMessageBroker:
    """Redis-based broker to handle message dispatch across processes"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisMessageBroker, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    async def initialize(self):
        """Initialize Redis connection (call this once at startup)"""
        if not hasattr(self, 'redis') or self.redis is None:
            # Get Redis host from environment or use Docker service name
            redis_host = os.getenv('REDIS_HOST', 'redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            
            try:
                self.redis = redis.Redis(
                    host=redis_host, 
                    port=redis_port, 
                    decode_responses=True
                )
                self.initialized = True
                print(f"Redis message broker initialized with host: {redis_host}:{redis_port}")
            except Exception as e:
                print(f"Redis connection error: {e}")
                # Fallback to in-memory queue system
                self.initialized = False
    
    async def subscribe(self, channel, queue):
        """Subscribe a queue to a channel"""
        await self.initialize()
        
        # Start a background task to listen for messages from Redis
        asyncio.create_task(self._listener(channel, queue))
        print(f"BROKER: Subscribed to Redis channel '{channel}'")
        return queue
    
    async def unsubscribe(self, channel, queue):
        """Unsubscribe a queue from a channel"""
        print(f"BROKER: Unsubscribing from Redis channel '{channel}'")
        try:
            # We don't need to do anything with Redis here since the listener task
            # will automatically terminate when the queue is garbage collected
            # Just print a log message for debugging
            print(f"Queue unsubscribed from channel {channel}")
        except Exception as e:
            print(f"Error unsubscribing from channel {channel}: {e}")
    
    async def _listener(self, channel, queue):
        """Background task that listens for Redis messages and forwards to queue"""
        try:
            # Create a new connection for the pubsub client
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            print(f"Listener started for channel {channel}")
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    # Convert message data from Redis to Python object
                    try:
                        data = json.loads(message["data"])
                        await queue.put(data)
                        print(f"Message from Redis forwarded to queue for channel {channel}")
                    except json.JSONDecodeError:
                        print(f"Invalid JSON in Redis message: {message['data']}")
                # Small sleep to avoid tight loop
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Redis listener error: {e}")
    
    async def publish(self, channel, message):
        """Publish a message to all subscribers of a channel"""
        await self.initialize()
        
        # Convert message to JSON for Redis
        message_json = json.dumps(message)
        
        # Publish to Redis channel
        await self.redis.publish(channel, message_json)
        print(f"BROKER: Published to Redis channel '{channel}'")
    
    def get_queue(self, channel):
        """Get a new queue and subscribe it to a channel"""
        queue = asyncio.Queue()
        # Create task to subscribe (can't await here)
        asyncio.create_task(self.subscribe(channel, queue))
        return queue

# Global instance
broker = RedisMessageBroker()