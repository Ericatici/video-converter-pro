import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

print("DEBUG: listeners.py imported", flush=True)

import pika
import json
from shared.config import settings
from .webhook import send_error_notification, send_completion_notification

print(f"DEBUG: Settings loaded. WEBHOOK_URL={settings.webhook_url}", flush=True)

def start_listening():
    """Start listening to video events from RabbitMQ"""
    print("🚀 Starting notification service listener...")
    print(f"📡 Connecting to RabbitMQ: {settings.rabbitmq_url}")
    print(f"🎯 Webhook target: {settings.webhook_url}")
    
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    channel = connection.channel()
    
    # Declare exchange
    channel.exchange_declare(exchange='video_events', exchange_type='topic', durable=True)
    
    # Declare queue and bind to events
    result = channel.queue_declare(queue='notification_queue', durable=True)
    queue_name = result.method.queue
    
    channel.queue_bind(exchange='video_events', queue=queue_name, routing_key='video.*')
    
    print(f"✅ Queue '{queue_name}' bound to 'video_events' exchange")
    
    def callback(ch, method, properties, body):
        """Process incoming events"""
        try:
            event_data = json.loads(body)
            routing_key = method.routing_key
            
            print(f"\n📨 Received event: {routing_key}")
            print(f"   Data: {event_data}")
            
            if routing_key == "video.completed":
                video_id = event_data.get("video_id")
                user_id = event_data.get("user_id")
                send_completion_notification(user_id, video_id)
            
            elif routing_key == "video.error":
                user_id = event_data.get("user_id")
                video_id = event_data.get("video_id")
                error = event_data.get("error", "Unknown error")
                send_error_notification(user_id, video_id, error)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"❌ Error processing event: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    
    print("👂 Listening for events...")
    print("Press CTRL+C to stop\n")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()
        print("\n⛔ Notification service stopped")

if __name__ == "__main__":
    try:
        start_listening()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
