package com.supremeai.controller;

import com.supremeai.model.FeatureDefinition;
import com.supremeai.response.ApiResponse;
import com.supremeai.service.FeatureRegistryService;
import com.supremeai.service.CodebaseAuditService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.List;

@RestController
@RequestMapping("/api/admin/features")
@RequiredArgsConstructor
public class FeatureRegistryController {

    private final FeatureRegistryService featureRegistryService;
    private final CodebaseAuditService codebaseAuditService;

    @GetMapping("/inventory")
    public ApiResponse<List<FeatureDefinition>> getFeatureInventory() {
        List<FeatureDefinition> features = featureRegistryService.getAllFeatures();
        return ApiResponse.ok(features);
    }

    @PostMapping("/register")
    public ApiResponse<String> registerFeature(@RequestBody FeatureDefinition feature) {
        // এক্সটেনশন থেকে আসা নতুন এজেন্ট বা ফিচার স্টোর করা
        featureRegistryService.register(feature);
        return ApiResponse.ok("Feature registered as " + feature.getStatus());
    }

    @PostMapping("/audit")
    public ApiResponse<String> triggerAudit() {
        codebaseAuditService.runAutoAudit();
        return ApiResponse.ok("Auto-Audit task completed. Check inventory for proposed features.");
    }
}