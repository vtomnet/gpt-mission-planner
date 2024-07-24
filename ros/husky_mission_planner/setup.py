from setuptools import find_packages, setup

package_name = 'husky_mission_planner'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='marcos',
    maintainer_email='mzuzuarregui@ucmerced.edu',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': ['husky_mission_planner = husky_mission_planner.mission_planner:main',
        ],
    },
)
