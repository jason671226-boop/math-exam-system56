import streamlit as st

def get_user_points(supabase, user_id):
    """查詢使用者剩餘點數"""
    try:
        res = supabase.table("profiles").select("points").eq("id", user_id).single().execute()
        return res.data.get("points", 0) if res.data else 0
    except Exception:
        st.error("查詢點數失敗，請稍後再試。")
        return 0

def deduct_user_points(supabase, user_id, points_to_deduct, reason="試卷產出"):
    """扣除使用者點數並記錄交易"""
    current_points = get_user_points(supabase, user_id)
    if current_points < points_to_deduct:
        return False, "點數不足"
    
    new_points = current_points - points_to_deduct
    try:
        # 更新點數
        supabase.table("profiles").update({"points": new_points}).eq("id", user_id).execute()
        # 新增對帳紀錄
        supabase.table("point_history").insert({
            "user_id": user_id,
            "amount": -points_to_deduct,
            "description": reason
        }).execute()
        return True, new_points
    except Exception:
        return False, "扣點失敗，請稍後再試。"
