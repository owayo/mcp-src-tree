import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

import pathspec
from mcp.server.fastmcp import FastMCP

# FastMCPサーバーの初期化
mcp = FastMCP("src-tree")


def read_gitignore(base_path: str) -> Optional[pathspec.PathSpec]:
    """
    .gitignoreファイルを読み込み、PathSpecオブジェクトを返す

    Args:
        base_path: .gitignoreファイルのあるベースディレクトリのパス

    Returns:
        PathSpecオブジェクト、.gitignoreが存在しない場合はNone
    """
    gitignore_path = os.path.join(base_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        return None

    with open(gitignore_path, "r") as f:
        # 空行とコメント行を除去
        lines = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]
        gitignore = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, lines
        )
    return gitignore


def should_ignore(
    path: str, base_path: str, gitignore: Optional[pathspec.PathSpec] = None
) -> bool:
    """
    指定されたパスを無視すべきかどうかを判定する

    Args:
        path: チェックするパス
        base_path: .gitignoreが存在するベースディレクトリのパス
        gitignore: .gitignoreのPathSpecオブジェクト

    Returns:
        無視すべき場合はTrue
    """
    # .で始まるディレクトリは無視
    if os.path.isdir(path) and os.path.basename(path).startswith("."):
        return True

    # .gitignoreの条件に一致するかチェック
    if gitignore:
        relative_path = os.path.relpath(path, base_path)
        # ディレクトリの場合は末尾にスラッシュを追加
        if os.path.isdir(path):
            relative_path = relative_path + os.sep
        # パスの正規化（スラッシュを統一）
        relative_path = relative_path.replace(os.sep, "/")
        if gitignore.match_file(relative_path):
            return True

    return False


def build_tree(
    path: str, base_path: str, gitignore: Optional[pathspec.PathSpec] = None, is_root: bool = True
) -> Dict[str, Any]:
    """
    ディレクトリのツリー構造を構築する

    Args:
        path: 走査するディレクトリのパス
        base_path: .gitignoreが存在するベースディレクトリのパス
        gitignore: .gitignoreのPathSpecオブジェクト
        is_root: ルートディレクトリかどうか

    Returns:
        ディレクトリツリーの辞書
    """
    # 無視すべきパスかチェック
    if should_ignore(path, base_path, gitignore):
        return None

    name = os.path.abspath(path) if is_root else os.path.basename(path)

    if os.path.isfile(path):
        return {"name": name, "type": "file"}

    result = {"name": name, "type": "directory", "children": []}

    try:
        items = os.listdir(path)
        for item in sorted(items):
            item_path = os.path.join(path, item)
            child = build_tree(item_path, base_path, gitignore, is_root=False)
            if child:
                result["children"].append(child)
    except PermissionError:
        pass

    return result


@mcp.prompt()
async def src_tree(directory: str) -> str:
    """
    ファイルツリーを取得する

    Returns:
        ファイルツリーのJSON文字列
    """
    if not os.path.exists(directory):
        return json.dumps({"error": "directory not found"}, indent=2)

    gitignore = read_gitignore(directory)
    tree = build_tree(directory, directory, gitignore)

    return json.dumps(tree, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_src_tree(directory: str) -> str:
    """
    指定されたディレクトリ配下のすべてのファイルツリーを返す

    Args:
        directory: 走査対象のディレクトリパス

    Returns:
        JSON形式のファイルツリー文字列
    """
    if not os.path.exists(directory):
        return json.dumps({"error": "directory not found"}, indent=2)

    gitignore = read_gitignore(directory)
    tree = build_tree(directory, directory, gitignore)

    return json.dumps(tree, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        mcp.run(transport="stdio")
    elif args[0] == "test" and len(args) == 2:
        # 非同期関数を実行するためのイベントループを作成
        result = asyncio.run(get_src_tree(args[1]))
        print(result)
