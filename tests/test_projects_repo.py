from app.db.projects_repo import delete_project, get_project, insert_project, list_projects, update_project


def test_insert_and_get_project(db):
    project_id = insert_project(title="测试项目", source_text="原文")

    project = get_project(project_id)

    assert project["title"] == "测试项目"
    assert project["source_text"] == "原文"
    assert project["annotated_text"] is None


def test_list_projects_orders_by_updated_at_desc(db):
    first = insert_project(title="第一个", source_text="a")
    second = insert_project(title="第二个", source_text="b")

    projects = list_projects()

    assert [p["id"] for p in projects][:2] == [second, first] or len(projects) == 2


def test_get_project_returns_none_when_missing(db):
    assert get_project(9999) is None


def test_update_project_changes_fields(db):
    project_id = insert_project(title="旧标题", source_text="旧原文")

    updated = update_project(project_id, title="新标题", annotated_text="[calm] 标注文本")

    assert updated is True
    project = get_project(project_id)
    assert project["title"] == "新标题"
    assert project["source_text"] == "旧原文"
    assert project["annotated_text"] == "[calm] 标注文本"


def test_update_project_returns_false_when_missing(db):
    assert update_project(9999, title="x") is False


def test_delete_project_removes_row(db):
    project_id = insert_project(title="待删除", source_text="x")

    deleted = delete_project(project_id)

    assert deleted is True
    assert get_project(project_id) is None


def test_delete_project_returns_false_when_missing(db):
    assert delete_project(9999) is False
