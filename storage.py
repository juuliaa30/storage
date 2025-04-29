from typing import Optional
from fastapi import FastAPI, Header, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pathlib import Path
from datetime import datetime
import shutil

app = FastAPI()
base_storage_path = Path("storage")


def resolve_safe_path(relative_path: str) -> Path:
    absolute_path = (base_storage_path / relative_path).resolve()
    if not absolute_path.is_relative_to(base_storage_path.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return absolute_path


@app.get("/files/{path:path}")
def read_file_or_directory(path: str):
    target_path = resolve_safe_path(path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    if target_path.is_file():
        return FileResponse(target_path, media_type="application/octet-stream", filename=target_path.name)

    if target_path.is_dir():
        file_list = []
        dir_list = []
        for entry in target_path.iterdir():
            if entry.is_file():
                file_list.append(entry.name)
            elif entry.is_dir():
                dir_list.append(entry.name)
        return JSONResponse(
            status_code=200,
            content={
                "files": file_list,
                "directories": dir_list
            }
        )


@app.head("/files/{path:path}")
def get_file_metadata(path: str):
    file_path = resolve_safe_path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    file_stats = file_path.stat()
    headers = {
        "Content-Length": str(file_stats.st_size),
        "Last-Modified": str(datetime.utcfromtimestamp(file_stats.st_mtime)),
    }
    return Response(headers=headers)


@app.put("/files/{path:path}")
async def create_or_copy_file(
        path: str,
        file: Optional[UploadFile] = File(None),
        copy_source: Optional[str] = Header(None, alias="X-Copy-From")
):
    destination_path = resolve_safe_path(path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if copy_source:
        source_path = resolve_safe_path(copy_source)
        if not source_path.exists() or not source_path.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        shutil.copy2(source_path, destination_path)
        return JSONResponse(status_code=200, content={"message": "File was copied"})

    if file is None:
        raise HTTPException(status_code=400, detail="File was not selected")

    with open(destination_path, "wb") as buffer:
        buffer.write(await file.read())
    return Response(status_code=201, content="File was loaded")


@app.delete("/files/{path:path}")
def remove_file_or_directory(path: str):
    item_path = resolve_safe_path(path)
    if not item_path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    try:
        if item_path.is_file():
            item_path.unlink()
        else:
            shutil.rmtree(item_path)
        return Response(status_code=204, content="File was successfully removed")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error: {error}")