package com.supremeai.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FeatureDefinition {
    private String id;
    private String name;
    private String category; // e.g., AI_MODEL, BROWSER_ENGINE, DEPLOYMENT
    private String provider; // e.g., Groq, Playwright, Cloud Run
    private String status;   // ACTIVE, DEPRECATED, EXPERIMENTAL
    private String description;
    private String classPath; // Reference to the implementation for quick changes
    private boolean isDuplicatePossible; // Flag to warn if similar logic exists
}