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
        if 'ingredients' in recipe_json:
            step = Step.objects.create(
                    instruction="s", space=self.request.space, show_ingredients_table=False,
                )
            ingredient_parser = IngredientParser(self.request, True)
            for ingredient in recipe_json['ingredients']:
                try:                     
                    if 'ingredient' in ingredient:
                        if 'name' in ingredient['ingredient']:
                            food = ingredient['ingredient']['name']
                    if 'quantity' in ingredient:
                        if 'amount' in ingredient['quantity']:
                            amount = ingredient['quantity']['amount']
                        if 'quantityType' in ingredient['quantity']:
                            unit = ingredient['quantity']['quantityType']
                            is_header = False
                        if ingredient['quantity']['quantityType'] == 'SECTION':
                            is_header = True
                            amount = 0
                            unit = None
                    f = ingredient_parser.get_food(food)
                    u = ingredient_parser.get_unit(unit)
                    step.ingredients.add(Ingredient.objects.create(
                        food=f, unit=u, amount=amount, is_header=is_header, original_text=ingredient, space=self.request.space,
                    ))
                except Exception:
                    pass
                recipe.steps.add(step)
                
        ingredients_added = False

        # FIXME: add "steps" as recipe directions
        if 'steps' in recipe_json:
            for direction in recipe_json['steps']:               
                try:
                    if 'step' in direction:
                        instruction = direction['step']
                        print(f'Step: {step.instruction}')
                    if 'order' in direction:
                        order = direction['order']
                        step = (Step.objects.create(
                            instruction=instruction,
                            order=order,
                            space=self.request.space
                        ))
                    else: 
                        step = (Step.objects.create(
                            instruction=instruction, 
                            space=self.request.space
                        ))

                        
                    recipe.steps.add(step)
                except Exception:   
                    pass
        
        # FIXME: add "notes" as recipe notes
        if 'notes' in recipe_json:
            try:
                notes = recipe_json['notes']
                recipe.steps.add(Step.objects.create(
                    name='Notes',
                    instruction=notes,
                    order=recipe.steps.count() + 1,
                    space=self.request.space
                ))
            except Exception:
                pass


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