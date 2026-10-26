package com.elmundo;

import java.util.HashMap;
import java.util.Map;

/** Shared checks so storage selection does not change attribute semantics. */
final class MetadataValueRules {
    private MetadataValueRules() { }

    static FilmDraft prepareDraft(FilmDraft draft, Map<String, AttributeFieldType> existingTypes)
            throws MetadataStoreException {
        if (draft == null) {
            throw new IllegalArgumentException("Film metadata is required.");
        }
        FilmDraft prepared = new FilmDraft();
        prepared.fillBlanksFrom(draft);
        prepared.getCustomFields().entrySet().removeIf(field ->
                !FilmDraft.hasText(field.getKey()) || !FilmDraft.hasText(field.getValue()));
        for (String name : prepared.getCustomFields().keySet()) {
            AttributeFieldType existing = existingTypes.get(AttributeHeaderMapper.normalizeHeader(name));
            if (existing != null && existing != AttributeFieldType.STRING) {
                throw new MetadataStoreException("Custom field '" + name + "' uses "
                        + existing.getDisplayName() + " values. Update it through attribute import.");
            }
        }
        return prepared;
    }

    static void validateAttributeTypes(AttributeImportData data,
            Map<String, AttributeFieldType> existingTypes) throws MetadataStoreException {
        Map<String, AttributeFieldType> types = new HashMap<>(existingTypes);
        for (AttributeImportColumn column : data.getImportableColumns()) {
            if (column.getTargetKind() != AttributeTargetKind.CUSTOM) {
                continue;
            }
            if (column.getFieldType() == null || column.getNormalizedName() == null) {
                throw new MetadataStoreException("Custom fields require a name and value type.");
            }
            AttributeFieldType expected = types.putIfAbsent(column.getNormalizedName(), column.getFieldType());
            if (expected != null && expected != column.getFieldType()) {
                throw new MetadataStoreException("Custom field '" + column.getHeader()
                        + "' already uses " + expected.getDisplayName() + " values.");
            }
        }
    }
}
