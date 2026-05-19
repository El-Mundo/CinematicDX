package com.elmundo;

@FunctionalInterface
public interface AttributeAmbiguityResolver {
    AttributeAmbiguityChoice resolve(AttributeAmbiguousRow row);
}
