import re
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class SensitivityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RedactionPattern:
    name: str
    pattern: re.Pattern
    replacement: str
    sensitivity: SensitivityLevel
    description: str


class SecurityRedacter:
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.private_registry = self._initialize_private_registry()
        self.redaction_log: List[Dict] = []
        
    def _initialize_patterns(self) -> List[RedactionPattern]:
        """Initialize regex patterns for detecting sensitive information."""
        return [
            RedactionPattern(
                name="email",
                pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                replacement="[EMAIL_REDACTED]",
                sensitivity=SensitivityLevel.MEDIUM,
                description="Email addresses"
            ),
            RedactionPattern(
                name="phone_us",
                pattern=re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'),
                replacement="[PHONE_REDACTED]",
                sensitivity=SensitivityLevel.MEDIUM,
                description="US phone numbers"
            ),
            RedactionPattern(
                name="ssn",
                pattern=re.compile(r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b'),
                replacement="[SSN_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="Social Security Numbers"
            ),
            RedactionPattern(
                name="credit_card",
                pattern=re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b'),
                replacement="[CREDIT_CARD_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="Credit card numbers"
            ),
            RedactionPattern(
                name="ipv4",
                pattern=re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
                replacement="[IP_REDACTED]",
                sensitivity=SensitivityLevel.LOW,
                description="IPv4 addresses"
            ),
            RedactionPattern(
                name="ipv6",
                pattern=re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'),
                replacement="[IP_REDACTED]",
                sensitivity=SensitivityLevel.LOW,
                description="IPv6 addresses"
            ),
            RedactionPattern(
                name="api_key",
                pattern=re.compile(r'\b(?:api[_-]?key|apikey|access[_-]?key|secret[_-]?key)[\s:=]+["\']?([A-Za-z0-9_\-]{20,})["\']?\b', re.IGNORECASE),
                replacement=r'api_key="[API_KEY_REDACTED]"',
                sensitivity=SensitivityLevel.CRITICAL,
                description="API keys and access tokens"
            ),
            RedactionPattern(
                name="jwt_token",
                pattern=re.compile(r'\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b'),
                replacement="[JWT_TOKEN_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="JWT tokens"
            ),
            RedactionPattern(
                name="aws_key",
                pattern=re.compile(r'\b(?:AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b'),
                replacement="[AWS_KEY_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="AWS access keys"
            ),
            RedactionPattern(
                name="password",
                pattern=re.compile(r'\b(?:password|passwd|pwd)[\s:=]+["\']?([^\s"\']{6,})["\']?\b', re.IGNORECASE),
                replacement=r'password="[PASSWORD_REDACTED]"',
                sensitivity=SensitivityLevel.CRITICAL,
                description="Passwords"
            ),
            RedactionPattern(
                name="private_key",
                pattern=re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
                replacement="[PRIVATE_KEY_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="Private cryptographic keys"
            ),
            RedactionPattern(
                name="url_with_credentials",
                pattern=re.compile(r'\b(?:https?|ftp)://[^\s:]+:[^\s@]+@[^\s]+\b'),
                replacement="[URL_WITH_CREDENTIALS_REDACTED]",
                sensitivity=SensitivityLevel.HIGH,
                description="URLs with embedded credentials"
            ),
            RedactionPattern(
                name="mac_address",
                pattern=re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b'),
                replacement="[MAC_ADDRESS_REDACTED]",
                sensitivity=SensitivityLevel.LOW,
                description="MAC addresses"
            ),
            RedactionPattern(
                name="date_of_birth",
                pattern=re.compile(r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12][0-9]|3[01])[/-](?:19|20)\d{2}\b'),
                replacement="[DOB_REDACTED]",
                sensitivity=SensitivityLevel.HIGH,
                description="Dates of birth (MM/DD/YYYY format)"
            ),
            RedactionPattern(
                name="passport",
                pattern=re.compile(r'\b[A-Z]{1,2}[0-9]{6,9}\b'),
                replacement="[PASSPORT_REDACTED]",
                sensitivity=SensitivityLevel.CRITICAL,
                description="Passport numbers"
            ),
        ]
    
    def _initialize_private_registry(self) -> Dict[str, Set[str]]:
        """Initialize hardcoded registry of private knowledge to filter."""
        return {
            "company_names": {
                "Acme Corporation",
                "TechStart Inc",
                "Global Industries Ltd",
                "SecureData Systems",
            },
            "project_codenames": {
                "Project Phoenix",
                "Operation Nightfall",
                "Initiative Alpha",
                "Codename Titan",
            },
            "internal_systems": {
                "InternalDB-PROD",
                "Legacy-System-2019",
                "CRM-Internal",
                "HR-Portal-v2",
            },
            "employee_names": {
                "John Smith",
                "Jane Doe",
                "Robert Johnson",
                "Emily Davis",
            },
            "locations": {
                "Building 7, Floor 3",
                "Research Lab A",
                "Data Center Alpha",
                "HQ Conference Room 401",
            },
            "proprietary_terms": {
                "QuantumSync Algorithm",
                "NeuralMesh Technology",
                "HyperScale Protocol",
                "SecureVault Encryption",
            },
            "internal_urls": {
                "internal.company.com",
                "intranet.corp.local",
                "vpn.internal.net",
                "admin.private.local",
            },
            "database_names": {
                "customers_db",
                "financial_records",
                "employee_data",
                "audit_logs",
            },
        }
    
    def add_to_registry(self, category: str, values: List[str]) -> None:
        """Add new values to the private registry."""
        if category not in self.private_registry:
            self.private_registry[category] = set()
        self.private_registry[category].update(values)
    
    def remove_from_registry(self, category: str, values: List[str]) -> None:
        """Remove values from the private registry."""
        if category in self.private_registry:
            self.private_registry[category].difference_update(values)
    
    def _apply_regex_patterns(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply regex patterns to redact sensitive information."""
        redacted_text = text
        matches = []
        
        for pattern_obj in self.patterns:
            found_matches = list(pattern_obj.pattern.finditer(redacted_text))
            if found_matches:
                for match in found_matches:
                    matches.append({
                        "type": pattern_obj.name,
                        "value": match.group(0),
                        "position": match.span(),
                        "sensitivity": pattern_obj.sensitivity.value,
                        "description": pattern_obj.description
                    })
                redacted_text = pattern_obj.pattern.sub(pattern_obj.replacement, redacted_text)
        
        return redacted_text, matches
    
    def _apply_registry_filters(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply registry-based filtering for private knowledge."""
        redacted_text = text
        matches = []
        
        for category, values in self.private_registry.items():
            for value in values:
                if value in redacted_text:
                    replacement = f"[{category.upper()}_REDACTED]"
                    count = redacted_text.count(value)
                    
                    for _ in range(count):
                        start_pos = redacted_text.find(value)
                        if start_pos != -1:
                            matches.append({
                                "type": f"registry_{category}",
                                "value": value,
                                "position": (start_pos, start_pos + len(value)),
                                "sensitivity": SensitivityLevel.HIGH.value,
                                "description": f"Private registry: {category}"
                            })
                    
                    redacted_text = redacted_text.replace(value, replacement)
        
        return redacted_text, matches
    
    def _apply_rule_based_methods(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply rule-based methods for context-aware redaction."""
        redacted_text = text
        matches = []
        
        suspicious_patterns = [
            (r'\b(?:confidential|secret|private|internal only|do not share)\b', re.IGNORECASE),
            (r'\b(?:salary|compensation|bonus)\s*[:=]\s*\$?[\d,]+(?:\.\d{2})?\b', re.IGNORECASE),
            (r'\b(?:username|user|login)\s*[:=]\s*["\']?([^\s"\']+)["\']?\b', re.IGNORECASE),
        ]
        
        for pattern_str, flags in suspicious_patterns:
            pattern = re.compile(pattern_str, flags)
            found_matches = list(pattern.finditer(redacted_text))
            
            if found_matches:
                for match in found_matches:
                    matches.append({
                        "type": "rule_based",
                        "value": match.group(0),
                        "position": match.span(),
                        "sensitivity": SensitivityLevel.HIGH.value,
                        "description": "Rule-based detection"
                    })
                redacted_text = pattern.sub("[SENSITIVE_INFO_REDACTED]", redacted_text)
        
        return redacted_text, matches
    
    def redact(self, text: str, enable_logging: bool = True) -> Dict:
        """
        Redact sensitive information from text using all available methods.
        
        Args:
            text: The text to redact
            enable_logging: Whether to log redaction details
            
        Returns:
            Dictionary containing redacted text and metadata
        """
        original_length = len(text)
        all_matches = []
        
        redacted_text, regex_matches = self._apply_regex_patterns(text)
        all_matches.extend(regex_matches)
        
        redacted_text, registry_matches = self._apply_registry_filters(redacted_text)
        all_matches.extend(registry_matches)
        
        redacted_text, rule_matches = self._apply_rule_based_methods(redacted_text)
        all_matches.extend(rule_matches)
        
        result = {
            "redacted_text": redacted_text,
            "original_length": original_length,
            "redacted_length": len(redacted_text),
            "matches_found": len(all_matches),
            "matches": all_matches,
            "sensitivity_summary": self._get_sensitivity_summary(all_matches)
        }
        
        if enable_logging:
            self.redaction_log.append(result)
        
        return result
    
    def _get_sensitivity_summary(self, matches: List[Dict]) -> Dict[str, int]:
        """Generate a summary of sensitivity levels found."""
        summary = {level.value: 0 for level in SensitivityLevel}
        for match in matches:
            sensitivity = match.get("sensitivity", SensitivityLevel.LOW.value)
            summary[sensitivity] = summary.get(sensitivity, 0) + 1
        return summary
    
    def get_redaction_log(self) -> List[Dict]:
        """Return the redaction log."""
        return self.redaction_log
    
    def clear_log(self) -> None:
        """Clear the redaction log."""
        self.redaction_log.clear()
    
    def get_statistics(self) -> Dict:
        """Get statistics about redactions performed."""
        if not self.redaction_log:
            return {"total_redactions": 0}
        
        total_matches = sum(log["matches_found"] for log in self.redaction_log)
        total_original_length = sum(log["original_length"] for log in self.redaction_log)
        total_redacted_length = sum(log["redacted_length"] for log in self.redaction_log)
        
        all_sensitivities = {}
        for log in self.redaction_log:
            for level, count in log["sensitivity_summary"].items():
                all_sensitivities[level] = all_sensitivities.get(level, 0) + count
        
        return {
            "total_redactions": len(self.redaction_log),
            "total_matches_found": total_matches,
            "total_original_length": total_original_length,
            "total_redacted_length": total_redacted_length,
            "average_matches_per_redaction": total_matches / len(self.redaction_log),
            "sensitivity_breakdown": all_sensitivities
        }


def main():
    """Example usage of the SecurityRedacter."""
    redacter = SecurityRedacter()
    
    sample_text = """
    Contact me at john.doe@example.com or call 555-123-4567.
    My SSN is 123-45-6789 and credit card is 4532015112830366.
    API Key: api_key="sk_live_1234567890abcdefghijklmnop"
    Password: mySecretPass123
    Internal system: InternalDB-PROD
    Working on Project Phoenix with Jane Doe at Building 7, Floor 3.
    Server IP: 192.168.1.100
    Confidential: Salary = $150,000
    """
    
    result = redacter.redact(sample_text)
    
    print("=" * 80)
    print("ORIGINAL TEXT:")
    print("=" * 80)
    print(sample_text)
    print("\n" + "=" * 80)
    print("REDACTED TEXT:")
    print("=" * 80)
    print(result["redacted_text"])
    print("\n" + "=" * 80)
    print("REDACTION SUMMARY:")
    print("=" * 80)
    print(f"Matches found: {result['matches_found']}")
    print(f"Sensitivity summary: {result['sensitivity_summary']}")
    print("\nDetailed matches:")
    for match in result["matches"]:
        print(f"  - {match['type']}: {match['description']} (Sensitivity: {match['sensitivity']})")
    
    print("\n" + "=" * 80)
    print("STATISTICS:")
    print("=" * 80)
    stats = redacter.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
