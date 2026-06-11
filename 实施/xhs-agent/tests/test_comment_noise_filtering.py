from platforms.comment_analysis import extract_comment_insights, is_noise_comment_text


def test_growth_group_promo_comment_is_noise() -> None:
    text = "给大家创建了一个提升成长的地方，里面都是一些优秀上进的伙伴们!欢迎一起提升，另外准备了一份小红书项目礼物，无偿分享位置不多，自行把握，看下面进4↓"

    assert is_noise_comment_text(text) is True


def test_noise_comments_do_not_create_fallback_insight() -> None:
    comments = [
        {
            "content": "给大家创建了一个提升成长的地方，里面都是一些优秀上进的伙伴们!欢迎一起提升，另外准备了一份小红书项目礼物，无偿分享位置不多，自行把握，看下面进4↓"
        }
    ]

    insights = extract_comment_insights("小红书新手选题方法", comments)

    assert insights == []
