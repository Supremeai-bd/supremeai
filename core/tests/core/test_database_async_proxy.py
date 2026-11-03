from unittest.mock import MagicMock

import pytest

from database.supabase_client import SupabaseDB

# বাংলা মন্তব্য: SupabaseDB-এর ডায়নামিক এসিঙ্ক প্রক্সি মেথডগুলোর সঠিক কার্যকারিতা পরীক্ষা করার জন্য ইউনিট টেস্ট।


@pytest.mark.anyio
async def test_supabase_db_dynamic_async_proxy():
    db_instance = SupabaseDB()

    # Mock self.client
    mock_client = MagicMock()
    db_instance.client = mock_client

    # Mock system_config table query return value
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_execute = MagicMock()

    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.execute.return_value = mock_execute
    mock_execute.data = [{"value": "async_val"}]

    # Call the dynamic async proxy get_config -> aget_config
    # বাংলা মন্তব্য: aget_config সরাসরি কোনো ফিজিক্যাল মেথড হিসেবে ডিফাইন করা নেই, এটি __getattr__ প্রক্সি দিয়ে রিডিরেক্ট হবে।
    res = await db_instance.aget_config("test_key")
    assert res == "async_val"

    mock_client.table.assert_called_once_with("system_config")
    mock_table.select.assert_called_once_with("value")
    mock_eq.execute.assert_called_once()
