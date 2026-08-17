# Documentation Templates

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  

---

## 📚 Templates Overview

This directory contains standardized templates for creating consistent, high-quality documentation across the SupremeAI 2.0 project.

### Available Templates

1. **[API_ENDPOINT_TEMPLATE.md](API_ENDPOINT_TEMPLATE.md)** - For documenting API endpoints
2. **[MODULE_DOCUMENTATION_TEMPLATE.md](MODULE_DOCUMENTATION_TEMPLATE.md)** - For documenting modules and components
3. **[FEEDBACK_COMPONENT.html](FEEDBACK_COMPONENT.html)** - Interactive feedback widget
4. **[test_documentation.py](test_documentation.py)** - Automated code example testing

---

## 🎯 How to Use Templates

### 1. API Endpoint Documentation

**When to use**: Documenting a new or existing API endpoint

**Steps**:
1. Copy `API_ENDPOINT_TEMPLATE.md`
2. Replace all `{placeholders}` with actual values
3. Fill in all sections
4. Test all code examples
5. Add verification steps

**Example**:
```bash
# Copy template
cp templates/API_ENDPOINT_TEMPLATE.md api/v1/endpoints/new-endpoint.md

# Edit and fill in placeholders
# {Endpoint Name} → "Create Agent"
# {file_path} → "api/v1/agents.py"
# {HTTP_METHOD} → "POST"
# {path} → "/agents"
```

---

### 2. Module Documentation

**When to use**: Documenting a new module, service, or component

**Steps**:
1. Copy `MODULE_DOCUMENTATION_TEMPLATE.md`
2. Replace all `{placeholders}` with actual values
3. Add class diagrams
4. Document all public methods
5. Add examples and tests

**Example**:
```bash
# Copy template
cp templates/MODULE_DOCUMENTATION_TEMPLATE.md services/llm/gateway.md

# Edit and fill in placeholders
# {Module Name} → "LLM Gateway"
# {file_path} → "services/llm/gateway.py"
# {ClassName} → "LLMGateway"
```

---

### 3. Feedback Component

**When to use**: Adding feedback mechanism to documentation pages

**Steps**:
1. Copy HTML from `FEEDBACK_COMPONENT.html`
2. Replace `{doc-id}` with unique document ID
3. Include JavaScript and CSS
4. Deploy feedback API endpoint

**Example**:
```html
<!-- At the end of your documentation -->
<div class="feedback-section" id="feedback-api-v1-agents">
  <!-- Paste feedback component HTML here -->
</div>

<script>
// Initialize feedback for this document
initFeedback('api-v1-agents');
</script>
```

---

### 4. Code Example Testing

**When to use**: Testing all code examples in documentation

**Steps**:
1. Run the test script
2. Review the report
3. Fix any failing examples
4. Integrate into CI/CD

**Example**:
```bash
# Run all documentation tests
python docs/knowledge-base/templates/test_documentation.py

# View report
cat docs/test_report.json

# Fix failing examples
# Re-run tests
```

---

## 📋 Template Checklist

### API Endpoint Template

- [ ] Endpoint name and path
- [ ] HTTP method
- [ ] Authentication requirements
- [ ] Request headers
- [ ] Path parameters
- [ ] Query parameters
- [ ] Request body schema
- [ ] Success response schema
- [ ] Error responses (400, 401, 403, 404, 429, 500)
- [ ] Code examples (cURL, Python, JavaScript, TypeScript)
- [ ] Verification steps
- [ ] Rate limiting info
- [ ] Common errors table
- [ ] Related documentation links

### Module Documentation Template

- [ ] Module name and location
- [ ] Module type (Service/Component/Utility/Model)
- [ ] Status (Active/Deprecated/Experimental)
- [ ] Owner/team
- [ ] Overview and purpose
- [ ] Architecture diagram
- [ ] Configuration options
- [ ] API reference (all public methods)
- [ ] Workflow diagrams
- [ ] Dependencies (internal and external)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Error handling
- [ ] Security considerations
- [ ] Monitoring metrics
- [ ] Lifecycle (init, startup, shutdown)
- [ ] Troubleshooting guide
- [ ] Examples (basic, advanced, integration)
- [ ] Related documentation
- [ ] Verification steps

---

## 🎨 Template Standards

### Formatting

- **Headers**: Use emoji indicators (📋, 🔐, 📥, 📤, etc.)
- **Code Blocks**: Always specify language
- **Tables**: Use Markdown tables for structured data
- **Lists**: Use bullet points for unordered, numbers for ordered
- **Links**: Use relative links for internal docs

### Placeholders

Placeholders are marked with `{curly_braces}` and should be replaced:

- `{Endpoint Name}` → "Create Agent"
- `{file_path}` → "api/v1/agents.py"
- `{type}` → "string", "int", "bool", etc.
- `{description}` → Actual description
- `{example}` → Working code example

### Required Sections

Every document must include:

1. **Header**: Version, date, status, classification
2. **Overview**: Purpose and scope
3. **Examples**: Working code examples
4. **Verification**: How to test/verify
5. **Related Docs**: Cross-references

---

## 🔄 Template Updates

### Version History

**v1.0.0** (2025-01-04):
- Initial templates created
- API endpoint template
- Module documentation template
- Feedback component
- Documentation testing script

### Contributing

To improve templates:

1. Test the template with real documentation
2. Identify missing sections
3. Propose changes via PR
4. Update version number
5. Update this README

---

## 📊 Template Usage

### Current Usage

| Template | Used For | Status |
|----------|----------|--------|
| API_ENDPOINT_TEMPLATE.md | All API endpoints | ✅ Active |
| MODULE_DOCUMENTATION_TEMPLATE.md | All modules | ✅ Active |
| FEEDBACK_COMPONENT.html | Documentation pages | ✅ Active |
| test_documentation.py | CI/CD testing | ✅ Active |

### Planned Templates

- [ ] COMPONENT_TEMPLATE.md - For React components
- [ ] TUTORIAL_TEMPLATE.md - For step-by-step tutorials
- [ ] TROUBLESHOOTING_TEMPLATE.md - For troubleshooting guides
- [ ] ADR_TEMPLATE.md - For Architecture Decision Records
- [ ] RUNBOOK_TEMPLATE.md - For operational runbooks

---

## ✅ Template Verification

**How to verify templates work**:

1. **Test API Template**:
   ```bash
   # Copy template
   cp templates/API_ENDPOINT_TEMPLATE.md test-api.md
   # Fill in placeholders
   # Verify all sections present
   ```

2. **Test Module Template**:
   ```bash
   # Copy template
   cp templates/MODULE_DOCUMENTATION_TEMPLATE.md test-module.md
   # Fill in placeholders
   # Verify all sections present
   ```

3. **Test Feedback Component**:
   ```bash
   # Open in browser
   open templates/FEEDBACK_COMPONENT.html
   # Test buttons
   # Verify styling
   ```

4. **Test Documentation Tester**:
   ```bash
   python templates/test_documentation.py
   # Should generate report
   # Should exit with 0 if all pass
   ```

---

## 🔗 Related Documentation

- [00-DOCUMENTATION_IMPROVEMENT_PLAN.md](../00-DOCUMENTATION_IMPROVEMENT_PLAN.md) - Improvement plan
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guide
- [31-ENGINEERING_PLAYBOOKS.md](../31-ENGINEERING_PLAYBOOKS.md) - Best practices

---

**Document Status**: ✅ Complete and Verified  
**Last Updated**: 2025-01-04  
**Owner**: Documentation Team  
**Classification**: Internal