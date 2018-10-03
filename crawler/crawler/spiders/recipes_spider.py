# import scrapy
#
#
# class QuotesSpider(scrapy.Spider):
#     name = "recipes"
#
#     def start_requests(self):
#         urls = [
#             'https://www.goodhousekeeping.com/food-recipes/dessert/a19293/apple-pie-recipe/'
#             # 'https://www.goodhousekeeping.com/food-recipes/a8806/lentil-kielbasa-garlic-stew-ghk0308/',
#             # "https://www.goodhousekeeping.com/food-recipes/easy/a22735786/shrimp-boil-with-sausage-and-spinach-recipe/",
#             # "https://www.goodhousekeeping.com/dinner-recipes/"
#             # "https://www.goodhousekeeping.com/food-recipes/easy/a19855090/ginger-pork-and-cucumber-salad-recipe/"
#         ]
#         for url in urls:
#             yield scrapy.Request(url=url, callback=self.parse)
#
#     def parse(self, response):
#         filename = 'apple-pie.html'
#         with open(filename, 'wb') as f:
#             f.write(response.body)
#         self.log('Saved file %s' % filename)


import scrapy
from scrapy.selector import Selector
from scrapy.http import HtmlResponse


class RecipesSpider(scrapy.Spider):
    name = "recipes"
    start_urls = [
        'https://www.goodhousekeeping.com/food-recipes/easy/',
        'https://www.goodhousekeeping.com/food-recipes/healthy/g448/salmon-recipes/',
        'https://www.goodhousekeeping.com/food-recipes/healthy/',
        'https://www.goodhousekeeping.com/easy-soup-recipes/',
        'https://www.goodhousekeeping.com/dinner-recipes/',
        'https://www.goodhousekeeping.com/food-recipes/dessert/',
        'https://www.goodhousekeeping.com/easy-chicken-recipes/'
    ]



    def parse(self, response):
        catagory = response.css('title::text').extract_first()
        for menu in response.css('a.full-item-image'):
            href = menu.css('a:nth-child(1)').xpath('@href').extract_first()
            url_list = href.split("/")
            url_list[-2] = url_list[-2].capitalize()
            url_list[-2] = url_list[-2].replace("-", " ")
            if url_list[-3][0] == 'a':
                item = {}
                item['category'] = catagory
                item['name'] = url_list[-2]
                item['picture'] = menu.css('img').xpath('@data-src').extract_first()
                item['ingredients'] =[]


                url = 'https://www.goodhousekeeping.com' + href

                if url is not None:

                    request = scrapy.Request(url, callback=self.parse_recipe_details,
                                      meta={'item': item})

                    yield request


    def parse_recipe_details(self, response):

        item = response.meta["item"]


        serving = response.css('span.yields-amount::text').extract_first()
        if len(serving) > 0:
            serving = [int(s) for s in serving.split() if s.isdigit()]
            item['servings'] = serving[0]
        else:
            item['servings'] = None

        time = response.css('span.total-time-amount::text').extract()
        if len(time) > 0:
            hour = int(time[0].strip())
            minute = int(time[1].strip())
            item['time'] = {'hour': hour, 'minute': minute}
        else:
            item['time'] = {'hour': None, 'minute': None}

        calories = response.css('span.cal-per-serv-amount::text').extract_first()
        if calories:
            cal = [int(s) for s in calories.split() if s.isdigit()]
            item['cal/serv'] = cal[0]
        else:
            item['cal/serv'] = None

        directions =  response.css('div.direction-lists li::text').extract()
        if len(directions) > 0:
            item['directions'] = directions
        else:
            directions = response.css('div.direction-lists p::text').extract()
            if len(directions) >0:
                item['directions'] = directions
            else: item['directions'] = []

        for ingredient in response.css('div.ingredient-item'):
            amount = ingredient.css('span.ingredient-amount::text').extract_first()
            description = ingredient.css('span.ingredient-description p::text').extract_first()
            description2 = ingredient.css('span.ingredient-description::text').extract_first()
            if amount and description:
                item['ingredients'].append({'amount': amount, 'description': description})
            elif description:
                item['ingredients'].append({'amount': None, 'description': description})
            elif description2:
                if amount is None:
                    item['ingredients'].append({'amount': None, 'description': description2})
                else:
                    item['ingredients'].append({'amount': amount, 'description': description2})

        return item
