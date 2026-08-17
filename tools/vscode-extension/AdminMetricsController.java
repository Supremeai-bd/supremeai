package com.supremeai.controller;

import com.supremeai.model.GlobalMetrics;
import com.supremeai.response.ApiResponse;
import com.supremeai.service.GlobalMetricsService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.CompletableFuture; // CompletableFuture ইম্পোর্ট করা হলো

@RestController
@RequestMapping("/api/admin/metrics")
@RequiredArgsConstructor
public class AdminMetricsController {

    private final GlobalMetricsService metricsService;

    @GetMapping("/summary")
    public CompletableFuture<ApiResponse<GlobalMetrics>> getGlobalSummary() {
        return metricsService.getGlobalStats().thenApply(ApiResponse::ok); // cite: 1
    }
}
