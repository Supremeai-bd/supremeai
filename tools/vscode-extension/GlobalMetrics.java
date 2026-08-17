package com.supremeai.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GlobalMetrics {
    private long patternsLearned;
    private long codeEdits;
    private long errorsReported;
    private long feedbackGiven;
    private long totalUsersActive;
}
