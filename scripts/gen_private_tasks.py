from agent_skill_bench.holdout import generate


def main() -> None:
    path = generate()
    print(path)


if __name__ == "__main__":
    main()
