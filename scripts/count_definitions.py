from apps.definitions.models import DefinitionItem, DefinitionTable

print("tables", DefinitionTable.objects.count())
print("items", DefinitionItem.objects.count())
