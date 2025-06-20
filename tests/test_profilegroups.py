import os
from pathlib import Path

from sas_bluesky.profile_groups import Profile, ProfileLoader

SAS_bluesky_ROOT = Path(__file__)

yaml_dir = os.path.join(
    SAS_bluesky_ROOT.parent.parent, "src", "sas_bluesky", "profile_yamls"
)

print(yaml_dir)


def test_profile_loader():
    config_filepath = os.path.join(yaml_dir, "panda_config.yaml")
    config = ProfileLoader.read_from_yaml(config_filepath)

    print(config)

    assert isinstance(config.profiles[0], Profile)


# def profile_loader_save():

#         P = Profile()
#     P.append_group(Group(frames=1,
#                          wait_time=1,
#                          wait_units="S",
#                          run_time=1,
#                          run_units="S",
#                          pause_trigger="IMMEDIATE",
#                          wait_pulses=[0,0,0,0],
#                          run_pulses=[1,1,1,1]))

#     json_schema = P.model_dump_json()


#     profile = Profile.model_validate(P)

#     new_profile = Profile.model_validate(from_json(json_schema, allow_partial=True))

#     print(new_profile)


#     dir_path = os.path.dirname(os.path.realpath(__file__))
#     config_filepath = os.path.join(dir_path,"profile_yamls","panda_config.yaml")


if __name__ == "__main__":
    # Run the test function
    test_profile_loader()
