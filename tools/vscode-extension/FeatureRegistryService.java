package com.supremeai.service;

import com.supremeai.model.FeatureDefinition;
import org.springframework.stereotype.Service;
import jakarta.annotation.PostConstruct;
import java.util.ArrayList;
import java.util.Objects;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class FeatureRegistryService {
    private final List<FeatureDefinition> registry = new ArrayList<>();

    @PostConstruct
    public void initRegistry() {
        // Register existing features to prevent duplicates
        register(FeatureDefinition.builder()
                .id("tiny-ai-v1")
                .name("Tiny AI Model")
                .category("AI_MODEL")
                .provider("On-Device SuperFly")
                .status("ACTIVE")
                .classPath("com.supremeai.ai.TinyAiEngine")
                .build());

        register(FeatureDefinition.builder()
                .id("godmode-3-browser")
                .name("Godmode 3 Browser")
                .category("BROWSER_ENGINE")
                .provider("Stateful Playwright")
                .status("ACTIVE")
                .classPath("com.supremeai.browser.GodmodeEngine")
                .build());

        register(FeatureDefinition.builder()
                .id("supreme-core-advanced")
                .name("SupremeAI Advanced Logic")
                .category("AI_MODEL")
                .provider("SupremeAI Logic Layer")
                .status("ACTIVE")
                .classPath("com.supremeai.service.ai.NvidiaKimiProvider")
                .build());
    }

    public void register(FeatureDefinition feature) {
        if (feature == null)
            return;

        // Enhanced logic to prevent actual duplicates in the inventory
        boolean isDuplicate = registry.stream()
                .anyMatch(f -> Objects.equals(f.getClassPath(), feature.getClassPath()) ||
                        Objects.equals(f.getId(), feature.getId()));

        if (!isDuplicate) {
            registry.add(feature);
        }
    }

    public List<FeatureDefinition> getAllFeatures() {
        return registry;
    }

    public List<FeatureDefinition> findByCategory(String category) {
        return registry.stream().filter(f -> f.getCategory().equalsIgnoreCase(category)).collect(Collectors.toList());
    }
}