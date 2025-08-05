import asyncio
from dither import applyDither
from PIL import Image, ImageFont, ImageDraw

CHARACTERISTIC_1 = "0000ff01-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_2 = "0000ff02-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_3 = "0000ff03-0000-1000-8000-00805f9b34fb"

class BluetoothDevice:
    def __init__(self, address: str):
        import bleak
        self.client = bleak.BleakClient(address)
        self.ready = True  # Flow control flag

    async def open(self):
        await self.client.connect()
        await self.client.start_notify(CHARACTERISTIC_1, self._notification_handler)
        await self.client.start_notify(CHARACTERISTIC_3, self._notification_handler)

    async def close(self):
        await self.client.disconnect()

    async def write(self, data):
        # Wait for printer to be ready before writing
        while not self.ready:
            await asyncio.sleep(0.01)
        
        self.ready = False  # Mark as busy
        await self.client.write_gatt_char(CHARACTERISTIC_2, data)
        
        # Small delay after write to prevent overwhelming the printer
        await asyncio.sleep(0.05)
        self.ready = True  # Mark as ready again

    def _notification_handler(self, sender, data):
        """处理BLE通知 with flow control"""
        print(f"BLE通知 - 发送者: {sender}, 数据: {data}")
        
        # Flow control responses
        if data == b"\x01\x05":  # Printer ready
            self.ready = True
        elif data == b"\x02\xc8\x00":  # Buffer status
            self.ready = True
        elif data == b"\x01\x01":  # Command acknowledged
            self.ready = True
        elif data == b"\xaa":
            print("接收到终止信号")
            self.ready = True

class LuckPrinter:
    def __init__(self, device):
        self.device = device
        self.width = 384
        self.brightness = 0.35
        self.contrast = 1.45
        self.density = 1

    async def initialize(self):
        await self.open()
        await self.enable()
        await self.disable_shutdown()

    async def open(self):
        await self.device.open()
    async def close(self):
        await self.device.close()

    async def enable(self):
        await self.device.write(bytes.fromhex("10FF40"))
        await asyncio.sleep(0.1)  # Wait between commands
        await self.device.write(bytes.fromhex("10FFF103"))
        await asyncio.sleep(0.1)

    async def print_end(self):
        await self.device.write(bytes.fromhex("1B4A64".rjust(256, "0")))
        await asyncio.sleep(0.1)
        await self.device.write(bytes.fromhex("10FFF145"))
        await asyncio.sleep(0.1)

    async def disable_shutdown(self):
        await self.device.write(bytes.fromhex("10FF120000"))
        await asyncio.sleep(0.1)

    async def print_text(self, text, font="zpix.ttf", font_size=20):
        font = ImageFont.truetype(font, font_size)
        content = ""
        line_length = 0
        for i, c in enumerate(text):
            if c == "\n":
                line_length = 0
                content += "\n"
                continue
            elif ord(c) <= 256:
                l = 0.5
            else:
                l = 1
            if line_length + l > self.width // font_size - 2:
                content += "\n"
                line_length = 0
            line_length += l
            content += c

        line_cnt = content.count("\n") + 1
        img = Image.new("RGB", (self.width, (font_size + 2) * line_cnt), "white")
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), str(content), fill="black", font=font)
        await self.print_image(img)

    async def print_image(self, img):
        img = img.convert("RGB")
        img = img.resize(
            (self.width, int(img.height * self.width / img.width)), Image.LANCZOS
        )
        imgHexStr = applyDither(
            img.size, img.load(), self.brightness, contrast=self.contrast**2
        )
        
        print(f"Image data length: {len(imgHexStr)} hex chars")
        
        # set density (0000 for low, 0100 for normal, 0200 for high)
        await self.device.write(bytes.fromhex(("10FF1000" + "0200").ljust(256, "0")))
        await asyncio.sleep(0.1)  # Wait after density setting
        
        hexlen = hex(int(len(imgHexStr) / 96) + 3)[2:]
        # little-endian for the length of hex lines
        fronthex = hexlen
        endhex = "0"
        if len(hexlen) > 2:
            fronthex = hexlen[1:3]
            endhex += hexlen[0:1]
        else:
            endhex += "0"
            
        # start command with data length
        print("Sending start command...")
        await self.device.write(
            bytes.fromhex(
                ("1D7630003000" + fronthex + endhex).ljust(32, "0") + imgHexStr[0:224]
            )
        )
        await asyncio.sleep(0.1)  # Wait after start command
        
        # send the image data in chunks WITH PROPER DELAYS
        print("Sending image data chunks...")
        chunk_count = 0
        for i in range(32 * 7, len(imgHexStr), 256):
            chunk_count += 1
            str_chunk = imgHexStr[i : i + 256]
            if len(str_chunk) < 256:
                str_chunk = str_chunk.ljust(256, "0")
            
            print(f"Sending chunk {chunk_count}...")
            await self.device.write(bytes.fromhex(str_chunk))
            
            # CRITICAL: Add delay between chunks to prevent disconnection
            await asyncio.sleep(0.1)  # Increased delay between chunks
            
        print("Image data sent successfully!")


async def main():
    device = BluetoothDevice("AA56CEF0-AA49-FD9B-0331-2C91D3622AA9")
    printer = LuckPrinter(device)

    try:
        await printer.initialize()
        await printer.print_text("Hello, Fixed Printer!")
        await printer.print_end()
        print("✅ Print completed successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await printer.close()


if __name__ == "__main__":
    asyncio.run(main())