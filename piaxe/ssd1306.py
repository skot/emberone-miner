try:
    import Adafruit_SSD1306
    from PIL import Image, ImageDraw, ImageFont
except:
    pass

RST = None

class SSD1306: 
    def __init__(self,stats):
        self.stats = stats

    def init(self):
        self.disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)
        self.disp.begin()
        self.disp.clear()
        self.disp.display()
        self.width = self.disp.width
        self.height = self.disp.height
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.load_default()
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

    def update(self):
        # Format temperature and hash rate with two decimal places
        formatted_temp = "{:.2f}".format(self.stats.temp)
        formatted_hash_rate = "{:.2f}".format(self.stats.hashing_speed)
        self.draw.text((0, 0), "Temp: " + formatted_temp, font=self.font, fill=255)
        self.draw.text((0, 10), "HR: " + formatted_hash_rate + " GH", font=self.font, fill=255)
        self.disp.image(self.image)
        self.disp.display()
