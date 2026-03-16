from argparse import Namespace
from unittest.mock import MagicMock, patch

from src.app.bootstrap import initialize_cache_manager
from src.app.workflow import DEFAULT_PHASES, execute_porting, run_modification_phases


def make_args(**overrides):
    base = {
        "stock": "stock.zip",
        "port": "port.zip",
        "ksu": False,
        "work_dir": "build",
        "clean": False,
        "debug": False,
        "pack_type": None,
        "fs_type": None,
        "eu_bundle": None,
        "phases": None,
        "cache_dir": ".cache/portroms",
        "no_cache": False,
        "enable_partition_cache": False,
        "clear_cache": False,
        "show_cache_stats": False,
    }
    base.update(overrides)
    return Namespace(**base)


def test_initialize_cache_manager_skips_official_mode():
    result = initialize_cache_manager(make_args(), is_official_modify=True, logger=MagicMock())

    assert result.cache_manager is None
    assert result.exit_code is None


def test_run_modification_phases_invokes_requested_modifiers():
    ctx = MagicMock()
    logger = MagicMock()

    with (
        patch("src.app.workflow.UnifiedModifier") as unified_modifier_cls,
        patch("src.app.workflow.FrameworkModifier") as framework_modifier_cls,
        patch("src.app.workflow.FirmwareModifier") as firmware_modifier_cls,
        patch("src.app.workflow.RomModifier") as rom_modifier_cls,
    ):
        unified_modifier = unified_modifier_cls.return_value
        unified_modifier.run.return_value = True

        run_modification_phases(ctx, ["system", "apk", "firmware"], logger)

    unified_modifier_cls.assert_called_once_with(ctx, enable_apk_mods=True)
    unified_modifier.run.assert_called_once_with(phases=["system", "apk"])
    framework_modifier_cls.assert_not_called()
    firmware_modifier_cls.assert_called_once_with(ctx)
    firmware_modifier_cls.return_value.run.assert_called_once()
    rom_modifier_cls.assert_called_once_with(ctx)
    rom_modifier_cls.return_value.run_all_modifications.assert_called_once()


def test_execute_porting_returns_zero_for_show_cache_stats():
    logger = MagicMock()
    args = make_args(show_cache_stats=True)

    with patch("src.app.workflow.initialize_cache_manager") as bootstrap:
        bootstrap.return_value.exit_code = 0
        bootstrap.return_value.cache_manager = None

        assert execute_porting(args, logger) == 0

    bootstrap.assert_called_once()


def test_execute_porting_uses_default_phase_list():
    logger = MagicMock()
    args = make_args()

    with (
        patch("src.app.workflow.initialize_cache_manager") as bootstrap,
        patch("src.app.workflow.log_run_configuration"),
        patch("src.app.workflow.OtaToolsManager") as otatools_manager_cls,
        patch("src.app.workflow.resolve_remote_inputs"),
        patch("src.app.workflow.resolve_work_paths") as resolve_work_paths,
        patch("src.app.workflow.RomPackage") as rom_package_cls,
        patch("src.app.workflow.PortingContext") as porting_context_cls,
        patch("src.app.workflow.load_device_config", return_value={}),
        patch("src.app.workflow.determine_pack_settings", return_value=("payload", "erofs")),
        patch("src.app.workflow.run_modification_phases") as run_modification_phases_mock,
        patch("src.app.workflow.run_repacking"),
    ):
        bootstrap.return_value.exit_code = None
        bootstrap.return_value.cache_manager = None
        otatools_manager_cls.return_value.ensure_otatools.return_value = True
        resolve_work_paths.return_value = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        stock = rom_package_cls.return_value
        porting_context = porting_context_cls.return_value
        porting_context.stock = stock
        porting_context.device_config = {}

        assert execute_porting(args, logger) == 0

    run_modification_phases_mock.assert_called_once()
    assert run_modification_phases_mock.call_args.args[1] == DEFAULT_PHASES
