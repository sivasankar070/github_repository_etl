CREATE TABLE if not exists repositories (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    description TEXT NOT NULL,
    html_url TEXT NOT NULL,
    private BOOLEAN,
    fork BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ,
    pushed_at TIMESTAMPTZ,
    size INT CHECK(size >= 0),
    stargazers_count INT CHECK(stargazers_count >= 0),
    forks_count INT CHECK(forks_count >= 0),
    open_issues_count INT CHECK(open_issues_count >= 0),
    language TEXT NOT NULL,
    visibility TEXT,
    archived BOOLEAN,
    disabled BOOLEAN,
    default_branch TEXT,
    CHECK(updated_at IS NOT NULL OR created_at <= updated_at)
);

CREATE TABLE if not exists repository_topics (
    repository_id BIGINT,
    topic TEXT,
    PRIMARY KEY (repository_id, topic),
    FOREIGN KEY (repository_id) REFERENCES repositories(id)
);