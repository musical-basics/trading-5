import asyncio
import json
import redis.asyncio as aioredis
import httpx

async def main():
    r = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    
    order_id = "test-alpaca-order-123"
    
    # Fake intents
    intents = [
        {"ticker": "AAPL", "side": "BUY", "quantity": 10, "price": 150.0, "portfolio_id": 1, "strategy_id": "momentum"},
        {"ticker": "AAPL", "side": "BUY", "quantity": 5, "price": 150.0, "portfolio_id": 2, "strategy_id": "low_beta"}
    ]
    
    payload = {
        "ticker": "AAPL",
        "intents": intents
    }
    
    await r.set(f"alpaca_order:{order_id}", json.dumps(payload))
    print("Set fake pending order in Redis.")
    
    # Trigger webhook
    webhook_data = {
        "event": "fill",
        "price": "151.0",
        "qty": "15",
        "order": {
            "id": order_id
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8000/api/execution/alpaca-webhook", json=webhook_data)
        print("Webhook Resp:", resp.json())
        
if __name__ == "__main__":
    asyncio.run(main())
