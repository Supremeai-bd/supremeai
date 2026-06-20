package com.supremeai.service;

import com.supremeai.model.GlobalMetrics;
import org.springframework.stereotype.Service;
import com.google.cloud.firestore.Firestore;
import com.google.cloud.firestore.FieldValue;
import lombok.RequiredArgsConstructor;

import java.util.concurrent.CompletableFuture; // CompletableFuture ইম্পোর্ট করা হলো

@Service
@RequiredArgsConstructor
public class GlobalMetricsService {

    private final Firestore firestore;
    private static final String METRICS_DOC = "system/global_metrics";

    // ফায়ারবেসে রিয়েল-টাইম ইনক্রিমেন্ট লজিক
    public void recordEdit() {
        // কোড এডিট সংখ্যা ১ বাড়ানো হচ্ছে
        firestore.document(METRICS_DOC).update("codeEdits", FieldValue.increment(1)); // cite: 1
    }

    public void recordError() {
        // এরর রিপোর্টের সংখ্যা বাড়ানো হচ্ছে
        firestore.document(METRICS_DOC).update("errorsReported", FieldValue.increment(1)); // cite: 1
    }

    public void recordFeedback() {
        firestore.document(METRICS_DOC).update("feedbackGiven", FieldValue.increment(1)); // cite: 1
    }

    // নতুন প্যাটার্ন লার্নিং রেকর্ড করার জন্য
    public void recordPattern() {
        firestore.document(METRICS_DOC).update("patternsLearned", FieldValue.increment(1)); // cite: 1
    }

    public CompletableFuture<GlobalMetrics> getGlobalStats() {
        return firestore.document(METRICS_DOC).get().toCompletableFuture().thenApply(documentSnapshot -> { // cite: 1
            if (documentSnapshot.exists()) { // cite: 1
                // Firestore থেকে সরাসরি GlobalMetrics অবজেক্টে ম্যাপ করা হচ্ছে
                return documentSnapshot.toObject(GlobalMetrics.class); // cite: 1
            } else {
                // যদি ডকুমেন্ট না থাকে, তাহলে ডিফল্ট/শূন্য মেট্রিক্স ফেরত দেওয়া হচ্ছে
                return GlobalMetrics.builder()
                        .patternsLearned(0)
                        .codeEdits(0)
                        .errorsReported(0)
                        .feedbackGiven(0)
                        .totalUsersActive(0) // এটি অন্য কোনো সার্ভিস থেকে আসতে পারে বা ডিফল্ট ০
                        .build();
            }
        });
    }
}
