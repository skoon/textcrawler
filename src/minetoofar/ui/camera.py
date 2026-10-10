"""Camera rule (GDD 5.1): the player may roam the middle third of the view before it scrolls."""


def follow_axis(cam: int, target: int, view: int, level: int) -> int:
    margin = view // 3
    if target < cam + margin:
        cam = target - margin
    elif target > cam + view - margin - 1:
        cam = target - (view - margin - 1)
    return max(0, min(cam, level - view))
