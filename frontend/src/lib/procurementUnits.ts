export const procurementUnitOptions = [
  { value: "шт", label: "шт" },
  { value: "компл", label: "компл" },
  { value: "упак", label: "упак" },
  { value: "короб", label: "короб" },
  { value: "пачка", label: "пачка" },
  { value: "кг", label: "кг" },
  { value: "г", label: "г" },
  { value: "л", label: "л" },
  { value: "мл", label: "мл" },
  { value: "м", label: "м" },
  { value: "кв. м", label: "кв. м" },
  { value: "куб. м", label: "куб. м" },
  { value: "рулон", label: "рулон" },
  { value: "пара", label: "пара" },
  { value: "услуга", label: "услуга" },
  { value: "час", label: "час" },
];

const procurementUnitLabels: Record<string, string> = {
  "шт": "штуки",
  "компл": "комплекты",
  "упак": "упаковки",
  "короб": "короба",
  "пачка": "пачки",
  "кг": "килограммы",
  "г": "граммы",
  "л": "литры",
  "мл": "миллилитры",
  "м": "метры",
  "кв. м": "кв. метры",
  "куб. м": "куб. метры",
  "рулон": "рулоны",
  "пара": "пары",
  "услуга": "услуги",
  "час": "часы",
};

type UnitAwareItem = {
  unit?: string | null;
};

const cleanUnitValue = (value?: string | null) => (
  String(value || "").trim().replace(/\s+/g, " ")
);

const normalizeUnit = (value?: string | null) => (
  cleanUnitValue(value).toLowerCase()
);

export const getProcurementUnitOptions = (currentUnit: string) => {
  const currentValue = cleanUnitValue(currentUnit);
  if (!currentValue || procurementUnitOptions.some((unit) => unit.value === currentValue)) {
    return procurementUnitOptions;
  }

  return [
    ...procurementUnitOptions,
    { value: currentValue, label: `${currentValue} (текущее)` },
  ];
};

export const getProcurementUnitLabel = (unit?: string | null) => {
  const normalizedUnit = normalizeUnit(unit);
  if (!normalizedUnit) {
    return "единиц";
  }
  return procurementUnitLabels[normalizedUnit] ?? normalizedUnit;
};

export const getProcurementQuantityUnitLabel = (
  items: UnitAwareItem[],
  fallbackLabel?: string | null,
) => {
  const normalizedFallback = String(fallbackLabel || "").trim();
  if (normalizedFallback) {
    return normalizedFallback;
  }

  const units = new Set(items.map((item) => normalizeUnit(item.unit)).filter(Boolean));
  if (units.size === 1) {
    return getProcurementUnitLabel([...units][0]);
  }

  return "единиц";
};
