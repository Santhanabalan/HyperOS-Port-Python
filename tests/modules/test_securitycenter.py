import pytest
from unittest.mock import call, ANY
from pathlib import Path
from src.modules.securitycenter import SecurityCenterModule

@pytest.fixture
def sec_module(base_fixtures):
    """Creates a SecurityCenterModule instance with mocked dependencies."""
    return SecurityCenterModule(base_fixtures["smali"], base_fixtures["ctx"])

def test_soh_patch_no_file(sec_module, base_fixtures, tmp_path):
    """Test SOH patch aborts gracefully if file not found."""
    # Run on empty tmp_path
    sec_module._patch_battery_health(tmp_path)
    
    # Assert no smali patch happened
    base_fixtures["smali"].assert_not_called()

def test_soh_patch_success(sec_module, base_fixtures, tmp_path):
    """Test SOH patch logic when file and field are found."""
    # Create fake smali file
    smali_file = tmp_path / "com/miui/powercenter/nightcharge/ChargeProtectFragment$d.smali"
    smali_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Content with required handleMessage and WeakReference field
    content = """
    .class public Lcom/miui/powercenter/nightcharge/ChargeProtectFragment$d;
    .field private myWeakRef:Ljava/lang/ref/WeakReference;
    
    .method public handleMessage(Landroid/os/Message;)V
        .locals 1
        return-void
    .end method
    """
    smali_file.write_text(content, encoding='utf-8')
    
    # Act
    sec_module._patch_battery_health(tmp_path)
    
    # Assert
    # Expect 2 calls: one for seek_keyword="battery_health_soh" (Writer), one for handleMessage (Reader)
    smali_mock = base_fixtures["smali"]
    assert smali_mock.call_count == 2
    
    # Verify Reader call (second call usually, but logic order matters)
    # The code calls Writer first (seek_keyword), then Reader (file_path)
    
    # Check 1st call (Writer)
    args1, kwargs1 = smali_mock.call_args_list[0]
    assert kwargs1.get('seek_keyword') == "battery_health_soh"
    assert "sys.hack.soh" in kwargs1.get('regex_replace')[1]
    
    # Check 2nd call (Reader)
    args2, kwargs2 = smali_mock.call_args_list[1]
    assert kwargs2.get('method') == "handleMessage"
    assert str(smali_file) == kwargs2.get('file_path')
    # Verify the field name 'myWeakRef' was correctly extracted and used in replacement code
    assert "myWeakRef" in kwargs2.get('regex_replace')[1]

def test_remove_intercept_timer(sec_module, base_fixtures, tmp_path):
    """Test removing intercept timer logic with strict tracing."""
    # 1. Setup Resource Structure
    res_dir = tmp_path / "res"
    values_cn = res_dir / "values-zh-rCN"
    values_cn.mkdir(parents=True, exist_ok=True)
    
    # 2. Mock strings.xml in zh-rCN
    (values_cn / "strings.xml").write_text(
        '<resources><string name="intercept_confirmed_text">确定（%d）</string></resources>',
        encoding='utf-8'
    )
    
    # 3. Mock XmlUtils.get_id to return a known ID
    # Since we are mocking XmlUtils, we just tell the mock what to return when asked for "intercept_confirmed_text"
    base_fixtures["xml"].get_id.side_effect = lambda path, name: "0x7f123456" if name == "intercept_confirmed_text" else None
    
    # 4. Setup Usage Smali (e.g. InterceptBaseFragment$1.smali)
    usage_smali = tmp_path / "smali/com/miui/permcenter/InterceptBaseFragment$1.smali"
    usage_smali.parent.mkdir(parents=True, exist_ok=True)
    
    # Content: initData calls getTimer() then uses the string ID
    usage_content = """
    .method public initData()V
        .locals 4
        
        # Call to be traced (invoke-virtual on this or other object)
        invoke-virtual {p0}, Lcom/miui/permcenter/InterceptBaseFragment;->getTimer()I
        move-result v0
        
        # Usage of ID
        const v1, 0x7f123456
        invoke-virtual {p0, v1}, Landroid/content/Context;->getString(I)Ljava/lang/String;
        
        return-void
    .end method
    """
    usage_smali.write_text(usage_content, encoding='utf-8')
    
    # 5. Setup Target Definition Smali (The actual file to patch)
    target_smali = tmp_path / "smali/com/miui/permcenter/InterceptBaseFragment.smali"
    target_smali.write_text(".class public Lcom/miui/permcenter/InterceptBaseFragment;", encoding='utf-8')
    
    # Act
    sec_module._remove_intercept_timer(tmp_path)
    
    # Assert
    # Verify smali_patch was called
    # We expect other patches too if we ran sec_module.run(), but we called _remove_intercept_timer directly.
    # So call_count should be 1.
    smali_mock = base_fixtures["smali"]
    assert smali_mock.call_count == 1
    
    args, kwargs = smali_mock.call_args
    
    # Verify it targeted the DEFINITION file, not the USAGE file
    assert str(target_smali) == kwargs['file_path']
    assert kwargs['method'] == "getTimer"
    assert kwargs['return_type'] == "I"
    assert "const/4 v0, 0x0" in kwargs['remake']
