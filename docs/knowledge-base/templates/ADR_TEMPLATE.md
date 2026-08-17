# ADR-{NUMBER}: {TITLE}

**Status**: {Proposed | Accepted | Rejected | Superseded}  
**Date**: {YYYY-MM-DD}  
**Authors**: {Name(s)}  
**Reviewers**: {Name(s)}  
**Supersedes**: {ADR-NUMBER if applicable}  
**Superseded by**: {ADR-NUMBER if applicable}

---

## 📋 Executive Summary

{One-paragraph summary of the decision and its impact}

**Decision**: {Brief statement of what was decided}

**Impact**: {High-level impact on the system}

---

## 🎯 Context

### Problem Statement

{Describe the problem or opportunity that motivated this decision}

**Current Situation**:
- {Current state 1}
- {Current state 2}
- {Current state 3}

**Pain Points**:
- {Pain point 1}
- {Pain point 2}
- {Pain point 3}

### Requirements

**Functional Requirements**:
- {Requirement 1}
- {Requirement 2}
- {Requirement 3}

**Non-Functional Requirements**:
- {Performance requirement}
- {Security requirement}
- {Scalability requirement}
- {Maintainability requirement}

### Constraints

**Technical Constraints**:
- {Constraint 1}
- {Constraint 2}

**Business Constraints**:
- {Constraint 1}
- {Constraint 2}

**Timeline Constraints**:
- {Deadline or milestone}

---

## 🔍 Options Considered

### Option 1: {Option Name}

**Description**: {Brief description}

**Pros**:
- ✅ {Advantage 1}
- ✅ {Advantage 2}
- ✅ {Advantage 3}

**Cons**:
- ❌ {Disadvantage 1}
- ❌ {Disadvantage 2}
- ❌ {Disadvantage 3}

**Cost Estimate**: {Time, Money, Resources}

**Risk Level**: {Low | Medium | High}

**Example**:
```python
# Example implementation
```

---

### Option 2: {Option Name}

**Description**: {Brief description}

**Pros**:
- ✅ {Advantage 1}
- ✅ {Advantage 2}

**Cons**:
- ❌ {Disadvantage 1}
- ❌ {Disadvantage 2}

**Cost Estimate**: {Time, Money, Resources}

**Risk Level**: {Low | Medium | High}

**Example**:
```python
# Example implementation
```

---

### Option 3: {Option Name}

**Description**: {Brief description}

**Pros**:
- ✅ {Advantage 1}

**Cons**:
- ❌ {Disadvantage 1}
- ❌ {Disadvantage 2}
- ❌ {Disadvantage 3}

**Cost Estimate**: {Time, Money, Resources}

**Risk Level**: {Low | Medium | High}

---

## ✅ Decision

### Chosen Option

**Option**: {Option number and name}

**Rationale**:
{Explain why this option was chosen over others}

**Key Factors**:
1. {Factor 1}: {Explanation}
2. {Factor 2}: {Explanation}
3. {Factor 3}: {Explanation}

---

## 📝 Implementation Plan

### Phase 1: {Phase Name} (Week 1-2)

**Tasks**:
- [ ] {Task 1}
- [ ] {Task 2}
- [ ] {Task 3}

**Deliverables**:
- {Deliverable 1}
- {Deliverable 2}

**Success Criteria**:
- {Criterion 1}
- {Criterion 2}

---

### Phase 2: {Phase Name} (Week 3-4)

**Tasks**:
- [ ] {Task 1}
- [ ] {Task 2}

**Deliverables**:
- {Deliverable 1}

**Success Criteria**:
- {Criterion 1}

---

### Phase 3: {Phase Name} (Week 5-6)

**Tasks**:
- [ ] {Task 1}
- [ ] {Task 2}

**Deliverables**:
- {Deliverable 1}

**Success Criteria**:
- {Criterion 1}

---

## 🎯 Consequences

### Positive Consequences

1. **{Benefit 1}**
   - {Explanation}
   - {Impact}

2. **{Benefit 2}**
   - {Explanation}
   - {Impact}

3. **{Benefit 3}**
   - {Explanation}
   - {Impact}

---

### Negative Consequences

1. **{Trade-off 1}**
   - {Explanation}
   - {Mitigation strategy}

2. **{Trade-off 2}**
   - {Explanation}
   - {Mitigation strategy}

---

### Neutral Consequences

1. **{Change 1}**
   - {Explanation}

2. **{Change 2}**
   - {Explanation}

---

## 🔒 Security Considerations

### Security Implications

- {Security aspect 1}
- {Security aspect 2}
- {Security aspect 3}

### Security Measures

- ✅ {Measure 1}
- ✅ {Measure 2}
- ✅ {Measure 3}

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| {Risk 1} | {Low/Med/High} | {Low/Med/High} | {Mitigation} |
| {Risk 2} | {Low/Med/High} | {Low/Med/High} | {Mitigation} |

---

## 📊 Performance Impact

### Expected Performance

| Metric | Current | Target | Actual |
|--------|---------|--------|--------|
| {Metric 1} | {value} | {value} | {value} |
| {Metric 2} | {value} | {value} | {value} |

### Performance Testing

```python
# Performance test example
async def test_performance():
    start = time.time()
    result = await operation()
    duration = time.time() - start
    
    assert duration < 100  # ms
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
def test_{feature}():
    """Test {specific aspect}"""
    # Test implementation
    pass
```

### Integration Tests

```python
async def test_{feature}_integration():
    """Test {feature} with real dependencies"""
    # Integration test
    pass
```

### Performance Tests

```python
def test_{feature}_performance():
    """Test {feature} meets performance requirements"""
    # Performance test
    pass
```

### Security Tests

```python
def test_{feature}_security():
    """Test {feature} security"""
    # Security test
    pass
```

---

## 📈 Success Metrics

### Quantitative Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| {Metric 1} | {value} | {value} | {How to measure} |
| {Metric 2} | {value} | {value} | {How to measure} |

### Qualitative Metrics

- {Qualitative measure 1}
- {Qualitative measure 2}

### Review Timeline

- **1 Week**: {What to check}
- **1 Month**: {What to check}
- **3 Months**: {What to check}
- **6 Months**: {What to check}

---

## 🔄 Migration Plan

### Migration Strategy

{Describe how to migrate from current state to new state}

### Migration Steps

1. **Preparation** (Week 1)
   - [ ] {Step 1}
   - [ ] {Step 2}

2. **Migration** (Week 2)
   - [ ] {Step 1}
   - [ ] {Step 2}

3. **Validation** (Week 3)
   - [ ] {Step 1}
   - [ ] {Step 2}

4. **Cleanup** (Week 4)
   - [ ] {Step 1}
   - [ ] {Step 2}

### Rollback Plan

**If migration fails**:
1. {Rollback step 1}
2. {Rollback step 2}
3. {Rollback step 3}

**Rollback triggers**:
- {Trigger 1}
- {Trigger 2}

---

## 👥 Stakeholders

### Affected Teams

| Team | Impact | Action Required |
|------|--------|-----------------|
| {Team 1} | {High/Med/Low} | {What they need to do} |
| {Team 2} | {High/Med/Low} | {What they need to do} |

### Communication Plan

- **Announcement**: {Date and channel}
- **Training**: {Date and format}
- **Documentation**: {What docs to update}
- **Support**: {How to get help}

---

## 📚 References

### Internal Documentation

- [Related ADR](../ADR-{NUMBER}.md)
- [Architecture Documentation](../03-ARCHITECTURE.md)
- [API Documentation](../11-API_DOCUMENTATION.md)

### External Resources

- [External Resource 1](https://...)
- [External Resource 2](https://...)
- [Industry Best Practice](https://...)

### Related Decisions

- {Related decision 1}
- {Related decision 2}

---

## 📝 Notes

### Open Questions

- {Question 1}
- {Question 2}

### Assumptions

- {Assumption 1}
- {Assumption 2}

### Dependencies

- {Dependency 1}
- {Dependency 2}

---

## ✅ Decision Checklist

Before finalizing this ADR, ensure:

- [ ] All options have been thoroughly evaluated
- [ ] Stakeholders have been consulted
- [ ] Security implications have been reviewed
- [ ] Performance impact has been assessed
- [ ] Migration plan is feasible
- [ ] Rollback plan is in place
- [ ] Success metrics are defined
- [ ] Documentation plan is ready
- [ ] Team consensus achieved

---

## 📊 ADR Metadata

**Decision Date**: {YYYY-MM-DD}  
**Implementation Date**: {YYYY-MM-DD}  
**Review Date**: {YYYY-MM-DD}  
**Status**: {Proposed | Accepted | Rejected | Superseded}  
**Priority**: {High | Medium | Low}  
**Risk Level**: {Low | Medium | High}  
**Effort Estimate**: {Story points or hours}  
**Actual Effort**: {To be filled after implementation}

---

## 🔄 Revision History

### Version 1.0.0 (YYYY-MM-DD)
- ✅ Initial proposal
- ✅ Options evaluated
- ✅ Decision made
- ✅ Implementation planned

### Version 1.1.0 (YYYY-MM-DD)
- 🔄 {Changes made}

---

**Document Status**: ✅ Complete and Approved  
**Next Review**: {YYYY-MM-DD}  
**Owner**: {Team/Person}  
**Classification**: {Internal | Confidential | Public}