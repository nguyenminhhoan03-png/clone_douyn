import asyncio
import edge_tts

async def run():
    for i in range(5):
        try:
            c = edge_tts.Communicate(f'Test {i}', 'vi-VN-NamMinhNeural', rate='+10%')
            await c.save(f'test{i}.mp3')
            print(f'Done {i}')
        except Exception as e:
            print(f'Error {i}: {e}')

asyncio.run(run())
