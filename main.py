import json

with open("data/warframes.json", encoding="utf-8") as f:
    datos = json.load(f)          # lista de diccionarios

nombre = input("Warframe: ").lower()
for w in datos:
    if w["name"].lower() == nombre:
        print(w["health"], w["shield"], w["armor"])
        for hab in w["abilities"]:
            print(hab["name"], "-", hab["description"])