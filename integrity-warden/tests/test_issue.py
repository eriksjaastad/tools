"""Tests for Issue dataclass."""

import pytest
from integrity_warden import Issue


class TestIssueHash:
    """Test Issue.__hash__() method."""
    
    def test_hash_consistency(self):
        """Test that same issues have same hash."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        
        assert hash(issue1) == hash(issue2)
    
    def test_hash_different_file(self):
        """Test that different files produce different hashes."""
        issue1 = Issue(
            file="test1.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        issue2 = Issue(
            file="test2.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        
        assert hash(issue1) != hash(issue2)
    
    def test_hash_different_type(self):
        """Test that different issue types produce different hashes."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken Markdown Link",
            target="MissingFile"
        )
        
        assert hash(issue1) != hash(issue2)
    
    def test_hash_different_target(self):
        """Test that different targets produce different hashes."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile1"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile2"
        )
        
        assert hash(issue1) != hash(issue2)
    
    def test_hash_ignores_context(self):
        """Test that different contexts don't change hash."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            context="context1"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            context="context2"
        )
        
        assert hash(issue1) == hash(issue2)
    
    def test_hash_ignores_severity(self):
        """Test that different severity doesn't change hash."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            severity="warning"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            severity="error"
        )
        
        assert hash(issue1) == hash(issue2)
    
    def test_hash_ignores_checker(self):
        """Test that different checker name doesn't change hash."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            checker="WikiLinkChecker"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            checker="OtherChecker"
        )
        
        assert hash(issue1) == hash(issue2)
    
    def test_hashable_in_set(self):
        """Test that issues can be added to sets."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue3 = Issue("test.py", "Broken WikiLink", "OtherFile")
        
        issue_set = {issue1, issue2, issue3}
        
        # Duplicates should be deduplicated in set
        assert len(issue_set) == 2


class TestIssueEquality:
    """Test Issue.__eq__() method."""
    
    def test_equality_same_values(self):
        """Test that issues with same values are equal."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        
        assert issue1 == issue2
    
    def test_equality_different_file(self):
        """Test that different files are not equal."""
        issue1 = Issue("test1.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test2.py", "Broken WikiLink", "MissingFile")
        
        assert issue1 != issue2
    
    def test_equality_different_type(self):
        """Test that different types are not equal."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test.py", "Broken Markdown Link", "MissingFile")
        
        assert issue1 != issue2
    
    def test_equality_different_target(self):
        """Test that different targets are not equal."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile1")
        issue2 = Issue("test.py", "Broken WikiLink", "MissingFile2")
        
        assert issue1 != issue2
    
    def test_equality_ignores_context(self):
        """Test that different contexts don't affect equality."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            context="context1"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            context="context2"
        )
        
        assert issue1 == issue2
    
    def test_equality_ignores_severity(self):
        """Test that different severity doesn't affect equality."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            severity="warning"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            severity="error"
        )
        
        assert issue1 == issue2
    
    def test_equality_ignores_checker(self):
        """Test that different checker doesn't affect equality."""
        issue1 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            checker="WikiLinkChecker"
        )
        issue2 = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            checker="OtherChecker"
        )
        
        assert issue1 == issue2
    
    def test_inequality_with_other_type(self):
        """Test inequality with non-Issue objects."""
        issue = Issue("test.py", "Broken WikiLink", "MissingFile")
        
        assert issue != "not an issue"
        assert issue != 42
        assert issue != None
        assert issue != {}
    
    def test_equality_reflexive(self):
        """Test that an issue is equal to itself."""
        issue = Issue("test.py", "Broken WikiLink", "MissingFile")
        assert issue == issue
    
    def test_equality_symmetric(self):
        """Test that equality is symmetric."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test.py", "Broken WikiLink", "MissingFile")
        
        assert issue1 == issue2
        assert issue2 == issue1
    
    def test_equality_transitive(self):
        """Test that equality is transitive."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue3 = Issue("test.py", "Broken WikiLink", "MissingFile")
        
        assert issue1 == issue2
        assert issue2 == issue3
        assert issue1 == issue3


class TestIssueDataclass:
    """Test Issue dataclass features."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        issue = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile"
        )
        
        assert issue.context == ""
        assert issue.severity == "warning"
        assert issue.checker == ""
    
    def test_all_fields_set(self):
        """Test creating issue with all fields."""
        issue = Issue(
            file="test.py",
            issue_type="Broken WikiLink",
            target="MissingFile",
            context="Found in [[MissingFile]]",
            severity="error",
            checker="WikiLinkChecker"
        )
        
        assert issue.file == "test.py"
        assert issue.issue_type == "Broken WikiLink"
        assert issue.target == "MissingFile"
        assert issue.context == "Found in [[MissingFile]]"
        assert issue.severity == "error"
        assert issue.checker == "WikiLinkChecker"
    
    def test_issue_in_list(self):
        """Test that issues can be stored in lists."""
        issues = [
            Issue("file1.py", "Type1", "target1"),
            Issue("file2.py", "Type2", "target2"),
        ]
        
        assert len(issues) == 2
        assert issues[0].file == "file1.py"
        assert issues[1].file == "file2.py"
    
    def test_issue_deduplication_in_set(self):
        """Test deduplication using set."""
        issue1 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue2 = Issue("test.py", "Broken WikiLink", "MissingFile")
        issue3 = Issue("test.py", "Broken WikiLink", "OtherFile")
        
        issues = [issue1, issue2, issue3]
        deduplicated = list(set(issues))
        
        assert len(deduplicated) == 2
    
    def test_severity_values(self):
        """Test different severity levels."""
        severities = ["info", "warning", "error"]
        
        for sev in severities:
            issue = Issue(
                file="test.py",
                issue_type="Test",
                target="target",
                severity=sev
            )
            assert issue.severity == sev
