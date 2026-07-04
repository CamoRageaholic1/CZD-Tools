# Seed a curated set of common whole foods into wger (per-100g macros).
# Idempotent: get_or_create keyed on (name, language=English id 2).
# Values are reasonable per-100g approximations for conversational calorie logging.
from decimal import Decimal
from wger.nutrition.models import Ingredient
from wger.core.models import Language

EN = Language.objects.get(short_name="en")

# name, energy(kcal), protein(g), carbohydrates(g), fat(g)  -- all per 100 g
FOODS = [
    # Proteins
    ("Chicken breast, cooked", 165, 31, 0, 3.6),
    ("Chicken thigh, cooked", 209, 26, 0, 11),
    ("Ground beef 85/15, cooked", 250, 26, 0, 15),
    ("Ground beef 90/10, cooked", 217, 26, 0, 12),
    ("Sirloin steak, cooked", 244, 27, 0, 15),
    ("Pork chop, cooked", 231, 26, 0, 14),
    ("Bacon, cooked", 541, 37, 1.4, 42),
    ("Salmon, cooked", 208, 20, 0, 13),
    ("Tuna, canned in water", 116, 26, 0, 1),
    ("Shrimp, cooked", 99, 24, 0.2, 0.3),
    ("Tilapia, cooked", 129, 26, 0, 2.7),
    ("Cod, cooked", 105, 23, 0, 0.9),
    ("Egg, whole", 143, 13, 1.1, 9.5),
    ("Egg white", 52, 11, 0.7, 0.2),
    ("Turkey breast, cooked", 135, 30, 0, 1),
    ("Ham, deli", 145, 19, 1.5, 6),
    ("Tofu, firm", 144, 17, 3, 9),
    ("Tempeh", 192, 20, 8, 11),
    ("Greek yogurt, plain nonfat", 59, 10, 3.6, 0.4),
    ("Cottage cheese, low-fat", 72, 12, 2.7, 1),
    ("Whey protein powder", 400, 80, 8, 6),
    # Dairy
    ("Milk, 2%", 50, 3.4, 4.8, 2),
    ("Milk, whole", 61, 3.2, 4.8, 3.3),
    ("Milk, skim", 34, 3.4, 5, 0.1),
    ("Cheddar cheese", 403, 25, 1.3, 33),
    ("Mozzarella cheese", 280, 28, 3.1, 17),
    ("Parmesan cheese", 431, 38, 4, 29),
    ("Butter", 717, 0.9, 0.1, 81),
    ("Cream cheese", 342, 6, 4, 34),
    # Grains / starches
    ("White rice, cooked", 130, 2.7, 28, 0.3),
    ("Brown rice, cooked", 123, 2.7, 26, 1),
    ("Pasta, cooked", 158, 6, 31, 0.9),
    ("White bread", 265, 9, 49, 3.2),
    ("Whole wheat bread", 247, 13, 41, 3.4),
    ("Bagel", 250, 10, 49, 1.5),
    ("Oats, dry", 389, 17, 66, 7),
    ("Quinoa, cooked", 120, 4.4, 21, 1.9),
    ("Flour tortilla", 312, 8, 50, 8),
    ("Potato, baked", 93, 2.5, 21, 0.1),
    ("Sweet potato, baked", 90, 2, 21, 0.1),
    ("Corn flakes cereal", 357, 7, 84, 0.4),
    ("Couscous, cooked", 112, 3.8, 23, 0.2),
    ("Crackers", 502, 9, 61, 25),
    # Vegetables
    ("Broccoli", 34, 2.8, 7, 0.4),
    ("Spinach", 23, 2.9, 3.6, 0.4),
    ("Carrot", 41, 0.9, 10, 0.2),
    ("Green beans", 31, 1.8, 7, 0.2),
    ("Tomato", 18, 0.9, 3.9, 0.2),
    ("Cucumber", 15, 0.7, 3.6, 0.1),
    ("Lettuce", 15, 1.4, 2.9, 0.2),
    ("Bell pepper", 31, 1, 6, 0.3),
    ("Onion", 40, 1.1, 9, 0.1),
    ("Mushrooms", 22, 3.1, 3.3, 0.3),
    ("Corn", 86, 3.2, 19, 1.2),
    ("Peas", 81, 5.4, 14, 0.4),
    ("Avocado", 160, 2, 9, 15),
    ("Cauliflower", 25, 1.9, 5, 0.3),
    ("Zucchini", 17, 1.2, 3.1, 0.3),
    ("Asparagus", 20, 2.2, 3.9, 0.1),
    ("Kale", 49, 4.3, 9, 0.9),
    ("Celery", 16, 0.7, 3, 0.2),
    # Fruits
    ("Banana", 89, 1.1, 23, 0.3),
    ("Apple", 52, 0.3, 14, 0.2),
    ("Orange", 47, 0.9, 12, 0.1),
    ("Strawberries", 32, 0.7, 7.7, 0.3),
    ("Blueberries", 57, 0.7, 14, 0.3),
    ("Grapes", 69, 0.7, 18, 0.2),
    ("Watermelon", 30, 0.6, 8, 0.2),
    ("Pineapple", 50, 0.5, 13, 0.1),
    ("Mango", 60, 0.8, 15, 0.4),
    ("Peach", 39, 0.9, 10, 0.3),
    ("Pear", 57, 0.4, 15, 0.1),
    ("Grapefruit", 42, 0.8, 11, 0.1),
    # Legumes / nuts
    ("Black beans, cooked", 132, 8.9, 24, 0.5),
    ("Chickpeas, cooked", 164, 8.9, 27, 2.6),
    ("Lentils, cooked", 116, 9, 20, 0.4),
    ("Kidney beans, cooked", 127, 8.7, 23, 0.5),
    ("Peanut butter", 588, 25, 20, 50),
    ("Almonds", 579, 21, 22, 50),
    ("Peanuts", 567, 26, 16, 49),
    ("Walnuts", 654, 15, 14, 65),
    ("Cashews", 553, 18, 30, 44),
    ("Hummus", 166, 8, 14, 10),
    # Fats / oils / sweeteners / condiments
    ("Olive oil", 884, 0, 0, 100),
    ("Mayonnaise", 680, 1, 0.6, 75),
    ("Ketchup", 101, 1.2, 25, 0.1),
    ("Honey", 304, 0.3, 82, 0),
    ("Maple syrup", 260, 0, 67, 0.1),
    ("Sugar", 387, 0, 100, 0),
    # Snacks / prepared / drinks
    ("Dark chocolate", 546, 4.9, 61, 31),
    ("Potato chips", 536, 7, 53, 35),
    ("Vanilla ice cream", 207, 3.5, 24, 11),
    ("Cheese pizza", 266, 11, 33, 10),
    ("French fries", 312, 3.4, 41, 15),
    ("Granola bar", 471, 8, 64, 20),
    ("Coffee, black", 1, 0.1, 0, 0),
    ("Orange juice", 45, 0.7, 10, 0.2),
    ("Beer", 43, 0.5, 3.6, 0),
    ("Red wine", 85, 0.1, 2.6, 0),
]

created = updated = 0
for name, e, p, c, f in FOODS:
    obj, was_created = Ingredient.objects.get_or_create(
        name=name, language=EN,
        defaults=dict(energy=int(e), protein=Decimal(str(p)),
                      carbohydrates=Decimal(str(c)), fat=Decimal(str(f))),
    )
    if was_created:
        created += 1
    else:
        obj.energy = int(e); obj.protein = Decimal(str(p))
        obj.carbohydrates = Decimal(str(c)); obj.fat = Decimal(str(f))
        obj.save()
        updated += 1

print(f"SEED_DONE created={created} updated={updated} total_english={Ingredient.objects.filter(language=EN).count()}")
