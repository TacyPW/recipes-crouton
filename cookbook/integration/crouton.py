import json
from io import BytesIO
from zipfile import ZipFile
import base64

from cookbook.helper.image_processing import get_filetype
from cookbook.helper.ingredient_parser import IngredientParser
from cookbook.helper.recipe_url_import import parse_duration, parse_time, parse_servings
from cookbook.integration.integration import Integration
from cookbook.models import Ingredient, Keyword, NutritionInformation, Recipe, Step

class Crouton(Integration):

    def import_file_name_filter(self, zip_info_object):
        return zip_info_object.filename.endswith('.crumb')
    
    def get_recipe_from_file(self, file):
        recipe_json = json.loads(file.getvalue().decode("utf-8"))

        recipe = Recipe.objects.create(
            name=recipe_json['name'].strip(),
            created_by=self.request.user, internal=True, space=self.request.space)
        
        if 'serves' in recipe_json:
            recipe.servings = parse_servings(recipe_json['serves'])
        if 'duration' in recipe_json:
            recipe.working_time = parse_time(recipe_json['duration'])
        if 'cookDuration' in recipe_json:
            recipe.waiting_time = parse_time(recipe_json['cookDuration'])
        if 'webLink' in recipe_json:
            recipe.source_url = recipe_json['webLink']

        # FIXME: add category and tags as keywords
        # if 'tags' in recipe_json:
        #     recipe.keywords.set(Keyword.objects.filter(name__in=recipe_json['tags']))
        # FIXME: add ingredients 

        # print(recipe_json.get('ingredients', None))
        
        if 'ingredients' in recipe_json:
            # step = Step.objects.create(space=self.request.space)
            ingredient_parser = IngredientParser(self.request, True)
            for ingredient in recipe_json['ingredients']:
                # print(ingredient.get('ingredient', dict).get('name', None))
                food = ingredient.get('ingredient', dict).get('name', None);
                #amount, unit, food, note = ingredient_parser.parse(ingredient)
                if ingredient.get('quantity', dict).get('quantityType', None) == 'SECTION':
                    amount = None
                    unit = None
                    is_header = True
                else:
                    amount = ingredient.get('quantity', dict).get('amount', None)
                    unit = ingredient.get('quantity', dict).get('quantityType', None)
                    is_header = False
                print(f'Amount: {amount}, Unit: {unit}, Food: {food}, Header: {is_header}')
                # amount = ingredient_parser.parse_amount(ingredient.quantity.amount)
                # unit = ingredient_parser.parse_unit(ingredient.quantity.quantityType) 
                # # FIXME: add note from ingredient.ingredient.name: parse between parentheses
                # food = ingredient_parser.parse_food(ingredient.ingredient.name)
                # f = ingredient_parser.get_food(food)
                # u = ingredient_parser.get_unit(unit)
                # recipe.ingredients.add(Ingredient.objects.create(
                #     food=f, unit=u, amount=amount, original_text=ingredient, space=self.request.space,
                # ))
            # recipe.steps.add(step)
        # FIXME: add "steps" as recipe directions

        # FIXME: add nutritional info - also accept the misspelling "neutritionalInfo"
        if 'nutritionalInfo' in recipe_json or 'neutritionalInfo' in recipe_json:
            nutrition = {}
            try:
                if 'calories' in recipe_json['nutrition']:
                    nutrition['calories'] = int(re.search(r'\d+', recipe_json['nutrition']['calories']).group())
                if 'proteinContent' in recipe_json['nutrition']:
                    nutrition['proteins'] = int(re.search(r'\d+', recipe_json['nutrition']['proteinContent']).group())
                if 'fatContent' in recipe_json['nutrition']:
                    nutrition['fats'] = int(re.search(r'\d+', recipe_json['nutrition']['fatContent']).group())
                if 'carbohydrateContent' in recipe_json['nutrition']:
                    nutrition['carbohydrates'] = int(re.search(r'\d+', recipe_json['nutrition']['carbohydrateContent']).group())

                if nutrition != {}:
                    recipe.nutrition = NutritionInformation.objects.create(**nutrition, space=self.request.space)
                    recipe.save()
            except Exception:
                pass

        if recipe_json.get("images", None):
            try:
                self.import_recipe_image(recipe, BytesIO(base64.b64decode(recipe_json['images'][0])), filetype='.PNG')
            except Exception:
                pass

        return recipe