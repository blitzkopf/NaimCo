import logging
import xml.etree.ElementTree as ET
import base64

_LOG = logging.getLogger(__name__)


def dict_to_etree(d):
    def _to_etree(parent, d):
        if not d:
            pass
        elif isinstance(d, str):
            parent.text = d
        elif isinstance(d, int):
            parent.text = str(d)
        elif isinstance(d, dict):
            for k, v in d.items():
                assert isinstance(k, str)
                _to_etree(ET.SubElement(parent, k), v)
        elif isinstance(d, list):
            for i in d:
                _LOG.debug(f"recursing this {i}")
                parent.append(dict_to_etree(i))
        else:
            assert d == "invalid type", (type(d), d)

    assert isinstance(d, dict) and len(d) == 1
    tag, data = next(iter(d.items()))
    root = ET.Element(tag)
    _to_etree(root, data)
    return root


def gen_xml_command(command, id, map=None):
    cmd = ET.Element("command")
    name = ET.SubElement(cmd, "name")
    name.text = command
    idel = ET.SubElement(cmd, "id")
    idel.text = id
    if map:
        cmd.append(dict_to_etree({"map": map}))
    return ET.tostring(cmd).decode("utf-8")


def tree_to_dict(element):
    if (tag := element.tag) in ["reply", "event", "item", "error"]:
        # name = element.attrib['name']
        me = {}
        val = None
        for k, v in element.items():
            match k:
                case "name":
                    name = v
                case "id":
                    me["id"] = v
                case "int":
                    val = int(v)
                case "string":
                    val = v
                case _:
                    raise NotImplementedError(f"Unknown attribute {k} in {tag}")
        for child in element:
            match child.tag:
                case "name":
                    name = child.text
                case "string":
                    val = child.text
                case "map":
                    val = {}
                    for item in child:
                        subtag, d = tree_to_dict(item)
                        val.update(d)
                case "array":
                    val = []
                    for item in child:
                        if item.tag == "map":
                            for it2 in item:
                                _LOG.debug(f"item: {ET.tostring(it2)}")
                                subtag, d = tree_to_dict(it2)
                                val.append(d)
                        else:
                            subtag, d = tree_to_dict(item)
                            val.append(d)
                case "base64":
                    val = base64.b64decode(child.text).decode("utf-8")
                case _:
                    if child.tag in ["id", "code", "description"]:
                        me[child.tag] = child.text
                    else:
                        raise NotImplementedError(f"Unknown child {child.tag} in {tag}")
        me[name] = val
        return tag, me
    raise NotImplementedError(f"Unknown element {element.tag}")


class MessageStreamProcessor:
    def __init__(self):
        self.parser = ET.XMLPullParser(["start", "end"])
        # fake tag to allow parsing of a stream og xml elements.
        # TODO: Figure out if this leaks memory.
        self.parser.feed("<stream>")
        self.lvl = 0
        self.tree_buffer = []

    def feed(self, data):
        self.parser.feed(data)
        for event, elem in self.parser.read_events():
            if event == "start":
                self.lvl += 1
            elif event == "end":
                self.lvl -= 1
                if self.lvl == 1:
                    # print(event)
                    # print(elem.tag, 'name=', elem.get('name'))
                    tag, dict = tree_to_dict(elem)
                    self.tree_buffer.append((tag, dict))

    def read_messages(self):
        res = iter(self.tree_buffer)
        self.tree_buffer = []
        return res
