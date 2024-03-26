import os
import json
import glob
import re
import ast
import math
import random
from matplotlib import cm
import subprocess
import numpy as np
import pydicom

from emptyseg.handle import check_n_replace_empty_mask, np_from_nifti
from emptyseg.create import create_empty_seg

processed_count = 0


def find_code_meaning(tag):
    result = None
    print("#####################################################")
    print("#")
    print(f"Searching for identical hit for {tag}...")
    tag = tag.lower()
    for entry in code_lookup_table:
        if tag.replace(" ", "-") == entry["Code Meaning"].lower().replace(" ", "-"):
            print(
                f"Found Code Meaning: {entry['Code Meaning'].lower()} for search term: {tag}"
            )
            result = entry
            break
        elif tag == entry["Body Part Examined"].lower():
            print(
                f"Found Code Meaning: {entry['Body Part Examined'].lower()} for search term: {tag}"
            )
            result = entry
            break

    if result == None:
        print(f"Nothing found -> Searching if {tag} is in one of the entires...")
        for entry in code_lookup_table:
            if tag in entry["Code Meaning"].lower():
                print(
                    f"Found Code Meaning: {entry['Code Meaning'].lower()} for search term: {tag}"
                )
                result = entry
                break
            elif tag in entry["Body Part Examined"].lower():
                print(
                    f"Found Code Meaning: {entry['Body Part Examined'].lower()} for search term: {tag}"
                )
                result = entry
                break

    if result == None:
        print(f"Nothing found -> Searching if {tag} parts equals one of the entires...")
        for entry in code_lookup_table:
            for tag_part in tag.split(" "):
                if tag_part == entry["Code Meaning"].lower():
                    print(
                        f"Found Code Meaning: {entry['Code Meaning'].lower()} for search term: {tag_part.lower()}"
                    )
                    result = entry
                    break
                elif tag_part == entry["Body Part Examined"].lower():
                    print(
                        f"Found Code Meaning: {entry['Body Part Examined'].lower()} for search term: {tag_part.lower()}"
                    )
                    result = entry
                    break
            if result != None:
                break

    if result == None:
        print(
            f"Nothing found -> Searching if {tag} parts can be found in one of the entires..."
        )
        for entry in code_lookup_table:
            for tag_part in tag.split(" "):
                if tag_part in entry["Code Meaning"].lower():
                    print(
                        f"Found Code Meaning: {entry['Code Meaning'].lower()} for search term: {tag_part.lower()}"
                    )
                    result = entry
                    break
                elif tag_part in entry["Body Part Examined"].lower():
                    print(
                        f"Found Code Meaning: {entry['Body Part Examined'].lower()} for search term: {tag_part.lower()}"
                    )
                    result = entry
                    break
            if result != None:
                break

    if result == None:
        print(
            f"Could not find the tag: '{tag}' in the lookup table, using custom entry"
        )
        result = {
            "Coding Scheme Designator": "Custom",
            "Code Value": "0.0.0.0.0.0.00000.0.000.0.00",
            "Code Meaning": f"{tag.replace('  ', ' '). lower()}",
            "Body Part Examined": "",
            "SNOMED-RT ID (Retired)": "",
            "FMA Code Value": None,
            "UMLS Concept UniqueID": "",
        }

    print("#")
    print("#####################################################")
    return result


def process_seg_info(seg_info, series_description):
    code_meaning = str(seg_info).lower()
    series_description_code_meaning = f"{code_meaning}"

    if series_description != "":
        return code_meaning, series_description
    else:
        return code_meaning, series_description_code_meaning


def create_segment_attribute(
    segment_algorithm_type,
    segment_algorithm_name,
    code_meaning,
    color,
    label_name="",
    labelID=1,
):
    try:
        search_key = (
            code_meaning.split("@")[-1].lower() if "@" in code_meaning else code_meaning
        )
        print("Searching coding-scheme for code-meaning: {}".format(code_meaning))
        print("Search-key: {}".format(search_key))
        coding_scheme = find_code_meaning(tag=search_key)
    except KeyError:
        raise AssertionError(
            f"The specified code meaning {code_meaning.lower()} does not exist. Check here for available code names: http://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_L.html#chapter_L from Table L-1."
        )

    segment_attribute = {}
    segment_attribute["labelID"] = labelID
    segment_attribute["SegmentAlgorithmType"] = segment_algorithm_type
    segment_attribute["SegmentAlgorithmName"] = segment_algorithm_name
    segment_attribute["recommendedDisplayRGBValue"] = color

    # segment_attribute["SegmentNumber"] = labelID
    segment_attribute["SegmentLabel"] = label_name
    segment_attribute["SegmentedPropertyCategoryCodeSequence"] = {
        "CodeValue": str(coding_scheme["Code Value"]),
        "CodingSchemeDesignator": coding_scheme["Coding Scheme Designator"],
        "CodeMeaning": code_meaning,
    }
    segment_attribute["SegmentedPropertyTypeCodeSequence"] = {
        "CodeValue": str(coding_scheme["Code Value"]),
        "CodingSchemeDesignator": coding_scheme["Coding Scheme Designator"],
        "CodeMeaning": code_meaning,
    }
    segment_attribute["SegmentedPropertyTypeModifierCodeSequence"] = {
        "CodeValue": str(coding_scheme["Code Value"]),
        "CodingSchemeDesignator": (
            coding_scheme["SNOMED-RT ID (Retired)"] if not math.isnan else "unkown"
        ),
        "CodeMeaning": code_meaning,
    }
    return segment_attribute


def adding_aetitle(element_input_dir, output_dcm_file, body_part):
    dcm_files = sorted(
        glob.glob(os.path.join(element_input_dir, "*.dcm*"), recursive=True)
    )

    if len(dcm_files) == 0:
        print("No dicom file found!")
        exit(1)

    dcm_file = dcm_files[0]
    print("dcm-file: {}".format(dcm_file))
    input_dicom = pydicom.dcmread(dcm_file)
    try:
        aetitle = input_dicom[0x0012, 0x0020].value
    except KeyError:
        aetitle = "internal"
    try:
        dicom_body_part = input_dicom[0x0018, 0x0015].value
    except KeyError:
        dicom_body_part = None

    dcmseg_file = pydicom.dcmread(output_dcm_file)
    print(f"# Adding aetitle:   {aetitle}")
    if body_part == "N/A" and dicom_body_part is not None:
        print(f"# Adding dicom-body_part: {dicom_body_part}")
        dcmseg_file.add_new(
            [0x0018, 0x0015], "LO", dicom_body_part
        )  # Body Part Examined
    elif body_part != "N/A":
        print(f"# Adding model-body_part: {body_part}")
        dcmseg_file.add_new([0x0018, 0x0015], "LO", body_part)  # Body Part Examined
    else:
        print("# Could not extract any body-part!")

    dcmseg_file.add_new([0x012, 0x020], "LO", aetitle)  # Clinical Trial Protocol ID
    dcmseg_file.save_as(output_dcm_file)


def force_update_content_tag_to_dicom(meta_attrs: dict, output_dcm_file):
    dcmseg_file = pydicom.dcmread(output_dcm_file)

    print(f"# Updating Content meta tags....")

    if "ContentLabel" in meta_attrs:
        content_label = dcmseg_file[0x0070, 0x0080]
        content_label.value = meta_attrs["ContentLabel"]

    if "ContentDescription" in meta_attrs:
        content_desc = dcmseg_file[0x0070, 0x0081]
        content_desc.value = meta_attrs["ContentDescription"]

    dcmseg_file.save_as(output_dcm_file)


# Example: https://github.com/QIICR/dcmqi/blob/master/doc/examples/seg-example.json
# SegmentedPropertyCategoryCodeSequence: Sequence defining the general category of the property the segment represents: https://dicom.innolitics.com/ciods/rt-structure-set/rt-roi-observations/30060080/00620003
# SegmentedPropertyTypeCodeSequence: https://dicom.innolitics.com/ciods/segmentation/segmentation-image/00620002/0062000f
# Note
# "Property" is used in the sense of meaning "what the segmented voxels represent", whether it be a physical or biological object, be real or conceptual, having spatial, temporal or functional extent or not. I.e., it is what the segment "is" (as opposed to some feature, attribute, quality, or characteristic of it, like color or shape or size).
# Only a single Item shall be included in this Sequence.
# http://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_L.html#chapter_L


print("Started: 'itkimage2segimage' ")
DCMQI = "/kaapana/app/dcmqi/bin"


# os.environ['BATCH_NAME'] = 'batch'
# os.environ['OPERATOR_IN_DIR'] = 'input'
# os.environ['WORKFLOW_DIR'] = '/home/klaus/private_data/jip-data/dcmqi/nnunet_test-200727123756236842/'

# # Case 1 single label segs with seg info
# os.environ['INPUT_TYPE'] = 'single_label_segs'
# os.environ['OPERATOR_IMAGE_LIST_INPUT_DIR'] = 'nnunet-predict_case1'
# os.environ['OPERATOR_OUT_DIR'] = 'nrrd2dcmseg_case1'
# os.environ['SINGLE_LABEL_SEG_INFO'] = 'right@kidney'

# # Case 2 single label seg info from file name
# os.environ['INPUT_TYPE'] = 'single_label_segs'
# os.environ['OPERATOR_IMAGE_LIST_INPUT_DIR'] = 'nnunet-predict_case2'
# os.environ['OPERATOR_OUT_DIR'] = 'nrrd2dcmseg_case2'
# os.environ['SINGLE_LABEL_SEG_INFO'] = 'from_file_name'

# # Case 3 Multiple single labels with creating of multi seg
# os.environ['INPUT_TYPE'] = 'single_label_segs'
# os.environ['OPERATOR_IMAGE_LIST_INPUT_DIR'] = 'nnunet-predict_case3'
# os.environ['OPERATOR_OUT_DIR'] = 'nrrd2dcmseg_case3'
# os.environ['SINGLE_LABEL_SEG_INFO'] = 'from_file_name'
# os.environ['CREATE_MULIT_LABEL_DCM_FROM_SINGLE_LABEL_SEGS'] = 'True'

# # Case 4 Multi label label segs input
# os.environ['INPUT_TYPE'] = 'multi_label_seg'
# os.environ['OPERATOR_IMAGE_LIST_INPUT_DIR'] = 'nnunet-predict_case4'
# os.environ['OPERATOR_OUT_DIR'] = 'nrrd2dcmseg_case4'
# os.environ['MULTI_LABEL_SEG_INFO_JSON'] = 'layer_info'
# os.environ['MULTI_LABEL_SEG_NAME'] = 'example multilabel'

# If input type is set to "multi_label_seg" you must create a json inside the OPERATOR_IMAGE_LIST_INPUT_DIR that contains the parts as follows: {"seg_info": ["spleen", "right@kidney"]}

input_type = os.environ.get("INPUT_TYPE")  # multi_label_seg or single_label_segs
multi_label_seg_name = (
    os.environ.get("MULTI_LABEL_SEG_NAME")
    if os.environ.get("MULTI_LABEL_SEG_NAME") not in [None, "None", ""]
    else "multi-label"
)  # Name used for multi-label segmentation object, if it will be created
segment_algorithm_name = os.environ.get("ALGORITHM_NAME", "kaapana")
segment_algorithm_type = os.environ.get("ALGORITHM_TYPE", "AUTOMATIC")
content_creator_name = os.environ.get("CREATOR_NAME", "kaapana")
series_description = os.environ.get("SERIES_DISCRIPTION", "")
series_number = os.environ.get("SERIES_NUMBER", "300")
instance_number = os.environ.get("INSTANCE_NUMBER", "1")
skip_empty_slices = (
    True if os.environ.get("SKIP_EMPTY_SLICES", "false").lower() == "true" else False
)
fail_on_no_segmentation_found = (
    True
    if os.environ.get("FAIL_ON_NO_SEGMENTATION_FOUND", "true").lower() == "true"
    else False
)
allow_empty_segmentation = (
    True
    if os.environ.get("ALLOW_EMPTY_SEGMENTATION", "false").lower() == "true"
    else False
)

empty_segmentation_label = int(os.environ.get("EMPTY_SEGMENTATION_LABEL", "99"))


def check_for_number_or_list(variable, space_replacement_char="~"):
    # Initially convert the variable into str and fix the space, that was replaced by
    # spacial character for passing through env variables.
    variable = str(variable).replace(space_replacement_char, " ")

    try:
        # Try evaluating the string as a Python literal
        value = ast.literal_eval(variable)
        # Check if the value is a number (int or float)
        if isinstance(value, (int, float)):
            return value  # Return the number
        elif isinstance(value, list):
            return value
    except (ValueError, SyntaxError):
        pass  # If literal_eval() fails or value is not a number, continue to the next step

    return variable  # Return the string as is if it's not a number


def extract_props_from_env_str(env_val: str):

    env_val = env_val.strip()
    if env_val == "":
        return {}

    # Split the string by the delimiter
    key_value_pairs = env_val.split(";")

    target_props = {}
    for pair in key_value_pairs:
        key, value = pair.split("=")
        key = check_for_number_or_list(key)
        # check values for tuples
        values = value.split(":")
        if len(values) > 1:
            tuple_key = values[0]
            tuple_val = values[1]
            tuple_values = tuple_val.split(",")
            # check if tuple value is a list then convert it into a list
            if len(tuple_values) > 1:
                tuple_val = [check_for_number_or_list(v) for v in tuple_values]
            value = (tuple_key, tuple_val)
        else:
            value = check_for_number_or_list(value)
        target_props[key] = value

    return target_props


## Curently not being used, as the dcmqi only support single segment mask
def update_seg_attribute_props(seg_attributes: list, seg_update_dict: dict):
    seg_labels = list(seg_update_dict.keys())
    for seg_item in seg_attributes:
        if isinstance(seg_item, list):
            seg_item = seg_item[0]

        seg_label = seg_item["labelID"]
        if seg_label in seg_labels:
            seg_updates = seg_update_dict[seg_label]
            update_key, update_val = seg_updates
            seg_item[update_key] = update_val
            seg_labels.remove(seg_label)

    if len(seg_labels) > 0:
        print(
            f"Segment attributes not found with the following labels {','.join(map(str, seg_labels))}. Provided values could not be updated."
        )

    return seg_attributes


def update_seg_attribute_props_single_segment(
    seg_attributes: list, seg_update_dict: dict
):
    """
    Update attributes of a single segment in a list of segment attributes based on a provided dictionary.

    Args:
        seg_attributes (list): List of segment attributes, where each segment is represented as a dictionary.
        seg_update_dict (dict): Dictionary containing attributes to update for the segment. applies
            update to all available segments, since now it only accept one segmentation mask.

    Returns:
        list: Updated list of segment attributes after applying the updates.

    """
    seg_attrs = list(seg_update_dict.keys())
    attr_list = seg_attributes
    if isinstance(seg_attributes, list):
        if len(seg_attributes) == 1:
            attr_list = seg_attributes[0]
        for seg_item in attr_list:
            seg_label = seg_item["labelID"]
            if not seg_label == 0:
                for attrs in seg_attrs:
                    seg_item[attrs] = seg_update_dict[attrs]
    elif isinstance(seg_attributes, dict):
        for attrs in seg_attrs:
            seg_attributes[attrs] = seg_update_dict[attrs]

    return seg_attributes


# Additional meta props environment variable value
meta_props_value = os.environ.get("ADDITIONAL_META_PROPS", "")
# Create a dictionary from the key-value pairs
meta_props = extract_props_from_env_str(meta_props_value)

seg_attribute_values = os.environ.get("SEGMENT_ATTRIBUTES_PROPS", "")
seg_attr_props = extract_props_from_env_str(seg_attribute_values)

get_seg_info_from_file = False
if input_type == "multi_label_seg":
    multi_label_seg_info_json = os.environ.get(
        "MULTI_LABEL_SEG_INFO_JSON", "seg_info.json"
    )  # name of json file that contain the parts as follows e.g. {"seg_info": ["spleen", "right@kidney"]}

    if multi_label_seg_info_json in [None, "None", ""]:
        multi_label_seg_info_json = "seg_info.json"

elif input_type == "single_label_segs":
    single_label_seg_info = os.environ.get(
        "SINGLE_LABEL_SEG_INFO"
    )  # SINGLE_LABEL_SEG_INFO must be either "from_file_name" or a e.g. "right@kidney"
    create_multi_label_dcm_from_single_label_segs = os.environ.get(
        "CREATE_MULIT_LABEL_DCM_FROM_SINGLE_LABEL_SEGS", "false"
    )  # true or false
    if single_label_seg_info == "":
        raise AssertionError(
            'SINGLE_LABEL_SEG_INFO must be either "from_file_name" or a e.g. "right@kidney"]}'
        )
    elif single_label_seg_info == "from_file_name":
        print("Seg info will be taken from file name")
        get_seg_info_from_file = True
    else:
        print(f"Taking {single_label_seg_info} as seg info")
else:
    raise NameError("Input_type must be either multi_label_seg or single_label_segs")


code_lookup_table_path = "code_lookup_table.json"
with open(code_lookup_table_path) as f:
    code_lookup_table = json.load(f)

batch_path = os.path.join("/", os.environ["WORKFLOW_DIR"], os.environ["BATCH_NAME"])

# check and create a empty nifti file in case
# no nifti file is created in the image_list input directory
# by the algorithm
if allow_empty_segmentation:
    create_empty_seg(
        batch_path,
        os.environ.get("BASE_NIFTI_DIR", ""),
        os.environ["OPERATOR_IMAGE_LIST_INPUT_DIR"],
    )


batch_folders = sorted([f for f in glob.glob(os.path.join(batch_path, "*"))])

print("Found {} batches".format(len(batch_folders)))

for batch_element_dir in batch_folders:
    print("process: {}".format(batch_element_dir))

    element_input_dir = os.path.join(batch_element_dir, os.environ["OPERATOR_IN_DIR"])
    input_image_list_input_dir = os.path.join(
        batch_element_dir, os.environ["OPERATOR_IMAGE_LIST_INPUT_DIR"]
    )

    if allow_empty_segmentation:
        check_n_replace_empty_mask(input_image_list_input_dir, empty_segmentation_label)

    element_output_dir = os.path.join(batch_element_dir, os.environ["OPERATOR_OUT_DIR"])
    if not os.path.exists(element_output_dir):
        os.makedirs(element_output_dir)

    segmentation_paths = []
    for endings in ("*.nii", "*.nii.gz", "*.nrrd"):
        segmentation_paths.extend(glob.glob(f"{input_image_list_input_dir}/{endings}"))

    if len(segmentation_paths) == 0:
        print(
            "Could not find valid segmentation file in {}".format(
                input_image_list_input_dir
            )
        )
        print("Supported: '*.nii', '*.nii.gz', '*.nrrd'")
        if fail_on_no_segmentation_found:
            print("abort!")
            exit(1)
        else:
            print(f"Skipping {input_image_list_input_dir}!")
            continue

    segmentation_information = {
        "@schema": "https://raw.githubusercontent.com/qiicr/dcmqi/master/doc/schemas/seg-schema.json#"
    }

    segmentation_information["ContentCreatorName"] = content_creator_name
    segmentation_information["SeriesNumber"] = series_number
    segmentation_information["InstanceNumber"] = instance_number

    # set the additional forwarded meta props to the segmentation information dict
    # for new meta data file
    if len(meta_props.keys()) > 0:
        for props in meta_props.keys():
            segmentation_information[props] = meta_props[props]

    if input_type == "single_label_segs":
        print("input_type == 'single_label_segs'")

        segment_attributes = []
        for idx, seg_filepath in enumerate(segmentation_paths):
            print(f"process idx: {idx} - {seg_filepath}")

            seg_filename = os.path.basename(seg_filepath)
            m = re.compile(r"(.*?)(\.nii.gz|\.nii|\.nrrd)").search(seg_filename)
            rootname = m.groups()[-2]

            if get_seg_info_from_file is True:
                single_label_seg_info = rootname

            (
                code_meaning,
                segmentation_information["SeriesDescription"],
            ) = process_seg_info(single_label_seg_info, series_description)
            color = (
                np.round(
                    np.array(cm.get_cmap("gist_ncar", 20)(random.randint(0, 19))[:3])
                    * 255
                )
                .astype(int)
                .tolist()
            )

            mask_np = np_from_nifti(seg_filepath)
            # Extract unique labels from the segmentation mask
            unique_mask_labels = list(np.unique(mask_np))
            if 0 in unique_mask_labels:
                unique_mask_labels.remove(0)

            labelID = 1
            if len(unique_mask_labels) > 0:
                labelID = int(unique_mask_labels[0])

            segment_attribute = create_segment_attribute(
                segment_algorithm_type,
                segment_algorithm_name,
                code_meaning,
                color,
                labelID=int(unique_mask_labels[0]),
            )

            if create_multi_label_dcm_from_single_label_segs.lower() == "true":
                segment_attributes.append([segment_attribute])

            if len(seg_attr_props.keys()) > 0:
                segment_attribute = update_seg_attribute_props_single_segment(
                    segment_attribute, seg_attr_props
                )

            segmentation_information["segmentAttributes"] = [[segment_attribute]]
            meta_data_file = f"{input_image_list_input_dir}/{rootname}.json"
            if os.path.isfile(meta_data_file):
                print("Wow, meta data file exsists already, taking this one!")
            else:
                with open(meta_data_file, "w") as write_file:
                    print("Writing JSON:: {}".format(meta_data_file))
                    json.dump(
                        segmentation_information, write_file, indent=4, sort_keys=True
                    )

            # Creating dcm_object
            output_dcm_file = f"{element_output_dir}/{rootname}.dcm"

            print("Starting dcmqi-subprocess for: {}".format(output_dcm_file))
            print(f"skip_empty_slices: {skip_empty_slices}")
            if skip_empty_slices:
                try:
                    dcmqi_command = [
                        f"{DCMQI}/itkimage2segimage",
                        "--skip",
                        "--inputImageList",
                        seg_filepath,
                        "--inputMetadata",
                        meta_data_file,
                        "--outputDICOM",
                        output_dcm_file,
                        "--inputDICOMDirectory",
                        element_input_dir,
                    ]
                    print("Executing", " ".join(dcmqi_command))
                    resp = subprocess.check_output(
                        dcmqi_command, stderr=subprocess.STDOUT
                    )
                    print(resp)
                except subprocess.CalledProcessError as e:
                    raise AssertionError(
                        f"Something weng wrong while creating the single-label-dcm object {e.output}"
                    )
            else:
                try:
                    dcmqi_command = [
                        f"{DCMQI}/itkimage2segimage",
                        "--inputImageList",
                        seg_filepath,
                        "--inputMetadata",
                        meta_data_file,
                        "--outputDICOM",
                        output_dcm_file,
                        "--inputDICOMDirectory",
                        element_input_dir,
                    ]
                    print("Executing", " ".join(dcmqi_command))
                    resp = subprocess.check_output(
                        dcmqi_command, stderr=subprocess.STDOUT
                    )
                    print(resp)
                except subprocess.CalledProcessError as e:
                    print(
                        f"The image seems to have empty slices, we will skip them! This might make the segmentation no usable anymore for MITK. Error: {e.output}"
                    )
                    raise AssertionError(
                        f"Something weng wrong while creating the single-label-dcm object {e.output}"
                    )

            adding_aetitle(element_input_dir, output_dcm_file, body_part="N/A")
            processed_count += 1

    elif input_type == "multi_label_seg":
        print("input_type == 'multi_label_seg'")

        json_path = os.path.join(input_image_list_input_dir, multi_label_seg_info_json)
        with open(json_path) as f:
            data = json.load(f)

        print("Loaded seg_info", data)

        if "seg_info" not in data:
            print(f"Could not find key 'seg_info' in json-file: {json_path}")
            print("Abort!")
            exit(1)

        label_info = data["seg_info"]

        body_part = "N/A"
        if "task_body_part" in data:
            body_part = data["task_body_part"]

        if "algorithm" in data:
            series_description = "{}-{}".format(
                segment_algorithm_name, data["algorithm"]
            )

        segment_attributes = [[]]

        label_counts = len(label_info)
        for idx, label in enumerate(label_info):
            label_int = int(label["label_int"])
            single_label_seg_info = label["label_name"]
            print(f"process: {single_label_seg_info}: {label_int}")
            if str(label_int) == "0":
                print("Clear Label -> skipping")
                continue

            (
                code_meaning,
                segmentation_information["SeriesDescription"],
            ) = process_seg_info(single_label_seg_info, series_description)
            color = (
                np.round(
                    np.array(cm.get_cmap("gist_ncar", label_counts)(idx)[:3]) * 255
                )
                .astype(int)
                .tolist()
            )
            segment_attribute = create_segment_attribute(
                segment_algorithm_type,
                segment_algorithm_name,
                code_meaning,
                color,
                label_name=single_label_seg_info,
                labelID=label_int,
            )
            segment_attributes[0].append(segment_attribute)

    if (
        input_type == "multi_label_seg"
        or create_multi_label_dcm_from_single_label_segs.lower() == "true"
    ):
        _, segmentation_information["SeriesDescription"] = process_seg_info(
            multi_label_seg_name, series_description
        )

        if len(seg_attr_props.keys()) > 0:
            segment_attributes = update_seg_attribute_props_single_segment(
                segment_attributes, seg_attr_props
            )

        segmentation_information["segmentAttributes"] = segment_attributes
        meta_data_file = (
            f"{input_image_list_input_dir}/{multi_label_seg_name.lower()}.json"
        )
        if os.path.isfile(meta_data_file):
            print("Wow, meta data file exsists already, taking this one!")
        else:
            with open(meta_data_file, "w") as write_file:
                print("Writing JSON:: {}".format(meta_data_file))
                json.dump(
                    segmentation_information, write_file, indent=4, sort_keys=True
                )

        output_dcm_file = f"{element_output_dir}/{multi_label_seg_name.lower()}.dcm"
        print("Output SEG.dcm file:: {}".format(output_dcm_file))
        print("Starting dcmqi-subprocess for: {}".format(output_dcm_file))
        print(f"skip_empty_slices: {skip_empty_slices}")
        if skip_empty_slices:
            try:
                dcmqi_command = [
                    f"{DCMQI}/itkimage2segimage",
                    "--skip",
                    "--inputImageList",
                    ",".join(segmentation_paths),
                    "--inputMetadata",
                    meta_data_file,
                    "--outputDICOM",
                    output_dcm_file,
                    "--inputDICOMDirectory",
                    element_input_dir,
                ]
                print("Executing", " ".join(dcmqi_command))
                resp = subprocess.check_output(dcmqi_command, stderr=subprocess.STDOUT)
                print(resp)
            except subprocess.CalledProcessError as e:
                raise AssertionError(
                    f"Something weng wrong while creating the multi-label-dcm object {e.output}"
                )
        else:
            try:
                dcmqi_command = [
                    f"{DCMQI}/itkimage2segimage",
                    "--inputImageList",
                    ",".join(segmentation_paths),
                    "--inputMetadata",
                    meta_data_file,
                    "--outputDICOM",
                    output_dcm_file,
                    "--inputDICOMDirectory",
                    element_input_dir,
                ]
                print("Executing", " ".join(dcmqi_command))
                resp = subprocess.check_output(dcmqi_command, stderr=subprocess.STDOUT)
                print(resp)
            except subprocess.CalledProcessError as e:
                print(
                    f"The image seems to have emtpy slices, we will skip them! This might make the segmentation no usable anymore for MITK. Error: {e.output}"
                )
                raise AssertionError(
                    f"Something weng wrong while creating the multi-label-dcm object {e.output}"
                )

        adding_aetitle(element_input_dir, output_dcm_file, body_part=body_part)
        if "ContentDescription" in meta_props or "ContentLabel" in meta_props:
            force_update_content_tag_to_dicom(meta_props, output_dcm_file)
        processed_count += 1


print("#")
print("#")
print("#")
print("#")
print(f"# Processed file_count: {processed_count}")
print("#")
print("#")
if processed_count == 0:
    print("#")
    print("##################################################")
    print("#")
    print("##################  ERROR  #######################")
    print("#")
    print("# ----> NO FILES HAVE BEEN PROCESSED!")
    print("#")
    print("##################################################")
    print("#")
    exit(1)
else:
    print("#")
    print(f"# ----> {processed_count} FILES HAVE BEEN PROCESSED!")
    print("#")
    print("# DONE #")
