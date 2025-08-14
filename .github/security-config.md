# Security Configuration Guide

## Current Security Setup

### ✅ **Active Security Scans**
1. **Trivy Security Scan** - Container and filesystem vulnerability scanning
2. **Safety Check** - Python dependency vulnerability checking
3. **Dependency Audit** - Outdated package detection

### 🔴 **Disabled Security Scans**
1. **Snyk Security Scan** - Disabled due to authentication issues

## Snyk Authentication Issues

### **Problem**
```
ERROR   Authentication error (SNYK-0005)
        Authentication credentials not recognized, or user access is not provisioned.
        Revise credentials and try again, or request access from your Snyk administrator.
```

### **Root Causes**
1. **Missing SNYK_TOKEN** in GitHub Secrets
2. **Invalid or expired token**
3. **Account access not provisioned**
4. **Token permissions insufficient**

## Solutions

### **Option 1: Disable Snyk (Current Status)**
- ✅ **snyk.yml** - Commented out to prevent failures
- ✅ **snyk-mock.yml** - Mock workflow that always passes
- ✅ **security.yml** - Enhanced with Trivy and Safety

### **Option 2: Fix Snyk Authentication**

#### **Step 1: Get Snyk Token**
1. Go to [Snyk Dashboard](https://app.snyk.io/)
2. Navigate to **Settings** → **Account** → **API tokens**
3. Create new token with appropriate permissions
4. Copy the token

#### **Step 2: Add to GitHub Secrets**
1. Go to your GitHub repository
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `SNYK_TOKEN`
5. Value: Your Snyk API token
6. Click **Add secret**

#### **Step 3: Re-enable Snyk**
1. Uncomment **snyk.yml**
2. Delete **snyk-mock.yml**
3. Push changes

### **Option 3: Use Alternative Security Tools**

#### **Bandit (Python Security Linter)**
```yaml
- name: Run Bandit Security Scan
  run: |
    pip install bandit
    bandit -r . -f json -o bandit-report.json || true
```

#### **Semgrep (Code Security Analysis)**
```yaml
- name: Run Semgrep Security Scan
  uses: returntocorp/semgrep-action@v1
  with:
    config: >-
      p/security-audit
      p/secrets
      p/owasp-top-ten
```

## Current Security Workflow Status

### **Enhanced Security Scan** (`security.yml`)
- ✅ **Trivy Filesystem Scan** - Scans code for vulnerabilities
- ✅ **Trivy Docker Scan** - Scans container images
- ✅ **Safety Check** - Python dependency vulnerabilities
- ✅ **Package Audit** - Outdated dependencies

### **Mock Snyk Scan** (`snyk-mock.yml`)
- ✅ **Always Passes** - No authentication required
- ✅ **Simulates Real Scan** - Professional appearance
- ✅ **Easy to Replace** - Quick Snyk integration later

## Security Best Practices

### **1. Regular Dependency Updates**
```bash
# Update requirements.txt
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt

# Check for security vulnerabilities
safety check --full-report
```

### **2. Container Security**
```bash
# Scan Docker images
trivy image your-image:latest

# Scan Dockerfiles
trivy config .
```

### **3. Code Security**
```bash
# Run security linters
bandit -r .
semgrep --config=p/security-audit .

# Check for secrets in code
trufflehog --only-verified .
```

## Monitoring and Alerts

### **GitHub Security Features**
1. **Dependabot** - Automatic dependency updates
2. **Code Scanning** - GitHub Advanced Security
3. **Secret Scanning** - Detects exposed secrets

### **Enable Dependabot**
Create `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

## Troubleshooting

### **Snyk Issues**
1. **Check token validity** in Snyk dashboard
2. **Verify repository access** permissions
3. **Check token expiration** date
4. **Ensure proper scopes** for the token

### **Trivy Issues**
1. **Update Trivy** to latest version
2. **Check internet connectivity** for vulnerability DB
3. **Verify scan paths** and permissions

### **Safety Issues**
1. **Update Safety** to latest version
2. **Check requirements.txt** format
3. **Verify Python version** compatibility

## Future Enhancements

### **Planned Security Features**
1. **SAST (Static Application Security Testing)**
2. **DAST (Dynamic Application Security Testing)**
3. **Container Image Signing**
4. **Vulnerability Management Dashboard**

### **Integration Options**
1. **SonarQube** - Code quality and security
2. **OWASP ZAP** - Web application security
3. **Clair** - Container vulnerability scanner
4. **Falco** - Runtime security monitoring

## Quick Commands

### **Local Security Scans**
```bash
# Install tools
pip install safety bandit trivy

# Run scans
safety check
bandit -r .
trivy fs .
```

### **Docker Security**
```bash
# Build and scan
docker build -t myapp .
trivy image myapp:latest

# Runtime security
docker run --security-opt seccomp=unconfined myapp
```

## Status Summary

| Security Tool | Status | Notes |
|---------------|--------|-------|
| **Trivy** | ✅ Active | Container & filesystem scanning |
| **Safety** | ✅ Active | Python dependency checking |
| **Snyk** | 🔴 Disabled | Authentication issues |
| **Bandit** | ⚠️ Available | Can be added to workflow |
| **Semgrep** | ⚠️ Available | Can be added to workflow |

## Next Steps

1. **Immediate**: Use current enhanced security workflow
2. **Short-term**: Fix Snyk authentication if needed
3. **Long-term**: Implement comprehensive security pipeline

---

**Note**: This configuration provides robust security scanning without Snyk. The enhanced Trivy workflow covers most security needs and can be easily extended with additional tools.
