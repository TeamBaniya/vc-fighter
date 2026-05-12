# test_pytgcalls.py
import asyncio
from pyrogram import Client
from pytgcalls import GroupCallFactory

async def main():
    # Create a dummy client for testing
    client = Client("test_session", in_memory=True)
    await client.start()
    
    # Get group call instance
    group_call = GroupCallFactory(client).get_group_call()
    
    # Print available methods
    methods = [x for x in dir(group_call) if not x.startswith('_')]
    print("Available methods:", methods[:20])  # Print first 20 methods
    
    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
