from typing import Tuple
import logging
from enum import Enum

from lxml import etree

from tasking import Task, GoToLocation, ActionType, TakePicture


# This defines the tag types throughout the schema document
class ElementTags(str, Enum):
    ACTION = "Action"
    ACTIONTYPE = "ActionType"
    ATOMICTASKS = "AtomicTasks"
    CONTROLCONSTRUCT = "ControlConstruct"
    PARAMETERS = "Parameters"
    PRECONDITION = "Precondition"
    PRECONDITIONS = "Preconditions"
    SEQUENCE = "Sequence"
    TASKID = "TaskID"


class MPDecoder:
    def __init__(self, schema_path: str, logger: logging.Logger):
        self.logger: logging.Logger = logger

        # schema related attributes
        self.namespace: str = None
        self.schema_path: str = schema_path

        # NOTE: these tasks will be put in order from first to last per mission plan (if order matters)
        self.task_list: list[Task] = []

    def validate_output(self, xml_file: str) -> Tuple[bool, str]:
        try:
            # Parse the XML file
            with open(xml_file, "rb") as xml_file:
                xml_doc = etree.parse(xml_file)

            # Validate the XML file against the XSD schema
            schema: etree.XMLSchema = etree.XMLSchema(file=self.schema_path)
            schema.assertValid(xml_doc)
            return True, "XML is valid."

        except etree.XMLSchemaError as e:
            return False, "XML is invalid: " + str(e)
        except Exception as e:
            return False, "An error occurred: " + str(e)

    def decode_xml_mp(self, xml_path: str):
        # parse the xml file
        mp: etree._ElementTree = etree.parse(xml_path)
        # get the root element <TaskTemplate>
        root: etree._Element = mp.getroot()
        # getting default ns with None (xmlns)
        self.namespace = "{" + root.nsmap[None] + "}"
        # find <ControlConstruct>
        cc: etree._Element = root.find(self.namespace + ElementTags.CONTROLCONSTRUCT)
        # find the <Sequence> within <ControlConstruct>
        tasks: etree._Element = cc.find(self.namespace + ElementTags.SEQUENCE)

        # iterate over all children to find all the tasks sequenced
        for child in tasks:
            if child is None:
                continue
            # names of tasks to identify with atomic descriptions
            task: Task = self._create_task(root, child.text)
            if task is not None:
                self.task_list.append(task)

    def _create_task(self, root: etree._Element, task_name: str) -> Task:
        """
        Helper function to create Task objects based on XML mission
        """
        # find <AtomicTasks> from root
        atomic_tasks = root.find(self.namespace + ElementTags.ATOMICTASKS)
        # find the <AtomicTask> in the list that matches the current task
        task = self._find_child(atomic_tasks, self.namespace + ElementTags.TASKID, task_name)

        # <Action>
        #   <Action>
        #       <ActionType>we want this string</ActionType>
        #       ...
        action_type: str = (
            task.find(self.namespace + ElementTags.ACTION)
            .find(self.namespace + ElementTags.ACTION)
            .find(self.namespace + ElementTags.ACTIONTYPE)
            .text
        )

        # ultimately this will become a waypoint for the waypoint follower node
        if action_type == ActionType.MOVETOLOCATION:
            self.logger.debug(f"Added AtomicTask: {action_type}")
            return GoToLocation(0, 0)
        elif action_type == ActionType.TAKETHERMALPICTURE:
            self.logger.debug(f"Added AtomicTask: {action_type}")
            # TODO: parse number of pictures
            return TakePicture(1)
        else:
            self.logger.error(f"Unsupported ActionType: {action_type}")
            return None

    def _find_child(self, root: etree._Element, tag_name: str, text: str):
        """
        Helper function to find a child based on interior text:
        root : current Element
        tag_name: tag name you're searching for text in
        text: text you're searching for
        
        <root>
            <tag_name>text</tag_name>
        </root>
        """
        for c in root:
            if c is None:
                continue
            task_id = c.find(tag_name)
            if task_id is None:
                continue
            # if you have a match
            if text == task_id.text:
                return c