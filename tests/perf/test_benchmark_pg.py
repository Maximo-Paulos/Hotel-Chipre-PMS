from tests.perf.benchmark_pg import index_usage_for_operation


def test_service_benchmarks_do_not_inherit_an_unrelated_explain_plan():
    plans = {"guest search": False, "availability": True}

    assert index_usage_for_operation("reservation.create_service", plans) is None
    assert index_usage_for_operation("reservation.create_auto_priced_service", plans) is None
    assert index_usage_for_operation("availability.find_available_rooms", plans) is None
    assert index_usage_for_operation("guest_search.document", plans) is None


def test_index_signal_is_limited_to_an_operation_with_a_matching_plan():
    plans = {
        "availability": True,
        "allocation": False,
        "balance": True,
        "daily report": False,
        "guest search": False,
    }

    assert index_usage_for_operation("availability.check_room_availability", plans) is True
    assert index_usage_for_operation("allocation.build_slots_from_db", plans) is False
    assert index_usage_for_operation("balance.balance_due_from_transactions", plans) is True
    assert index_usage_for_operation("daily_report", plans) is False
    assert index_usage_for_operation("guest_search.last_name", plans) is False
