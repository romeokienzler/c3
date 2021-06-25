class  BaseComponentSpec():
    def get_name() -> str:
        raise Exception("Not implemented")

    def get_description() -> str:
        raise Exception("Not implemented")

    def get_inputs() -> List[Dict[str,str]]:
        raise Exception("Not implemented")

    def get_outputs() -> List[Dict[str,str]]:
        raise Exception("Not implemented")

    def get_container_uri() -> str:
        raise Exception("Not implemented")

    def get_requirements() -> List[str]:
        raise Exception("Not implemented")