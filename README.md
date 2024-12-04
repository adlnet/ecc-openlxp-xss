# OPENLXP-XSS - Experience Schema Service 

The Experience Schema Service (XSS) maintains referential representations of domain entities, as well as transformational mappings that describe how to convert an entity from one particular schema representation to another.

This component responsible for managing pertinent object/record metadata schemas, and the mappings for transforming records from a source metadata schema to a target metadata schema. This component will also be used to store and link vocabularies from stored schema.


## Prerequisites
### Install Docker & docker-compose
#### Windows & MacOS
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop) (docker compose included)


#### Linux
You can download Docker Compose binaries from the
[release page](https://github.com/docker/compose/releases) on this repository.

Rename the relevant binary for your OS to `docker-compose` and copy it to `$HOME/.docker/cli-plugins`

Or copy it into one of these folders to install it system-wide:

* `/usr/local/lib/docker/cli-plugins` OR `/usr/local/libexec/docker/cli-plugins`
* `/usr/lib/docker/cli-plugins` OR `/usr/libexec/docker/cli-plugins`

(might require making the downloaded file executable with `chmod +x`)

### Python
`Python >=3.9` : Download and install it from here [Python](https://www.python.org/downloads/).


## 1. Clone the project
Clone the Github repository
```
git clone https://github.com/OpenLXP/openlxp-xss.git
```  

## 2. Set up your environment variables
- Create a `.env` file in the root directory
- The following environment variables are required:

| Environment Variable      | Description |
| ------------------------- | ----------- |
| AWS_ACCESS_KEY_ID         | The Access Key ID for AWS  |
| AWS_SECRET_ACCESS_KEY     | The Secret Access Key for AWS  |
| AWS_DEFAULT_REGION        | The region for AWS |
| DB_HOST                   | The host name, IP, or docker container name of the database |
| DB_NAME                   | The name to give the database |
| DB_PASSWORD               | The password for the user to access the database |
| DB_ROOT_PASSWORD          | The password for the root user to access the database, should be the same as `DB_PASSWORD` if using the root user |
| DB_USER                   | The name of the user to use when connecting to the database. When testing use root to allow the creation of a test database |
| DJANGO_SUPERUSER_EMAIL    | The email of the superuser that will be created in the application |
| DJANGO_SUPERUSER_PASSWORD | The password of the superuser that will be created in the application |
| DJANGO_SUPERUSER_USERNAME | The username of the superuser that will be created in the application |
| LOG_PATH                  | The path to the log file to use |
| SECRET_KEY_VAL            | The Secret Key for Django |

## 3. Deployment
1. Create the OpenLXP docker network. Open a terminal and run the following command in the root directory of the project
    ```
    docker network create openlxp
    ```

2. Run the command below to deploy XSS along with it's resources
    ```
    docker-compose up -d --build
    ```

## 4. Configuration for XSS
1. Navigate over to `http://localhost:8000/admin/` in your browser and login to the Django Admin page with the admin credentials set in your `.env` (`DJANGO_SUPERUSER_EMAIL` & `DJANGO_SUPERUSER_PASSWORD`)

2. <u>CORE</u>
    - Schema Ledgers
        1. Click on `Schema Ledgers` > `Add schema ledgers`
            - Enter the configurations below:

                - `Schema Name`: Schema file title

                - `Schema File` Upload the Schema file in the required format(JSON)

                - `Status` Select if the Schema is Published or Retired

                - `Major version` Add the Major value of the schema version

                - `Minor Version` Add the Minor value of the schema version

                - `Patch Version` Add the Patch version number of the schema 

            **Note: On uploading the schema file in the required format to the schema ledger the creation of corresponding term set, linked child term set and terms process is triggered.**

    - Transformation Ledger
        1. Click on `Transformation Ledgers` > `Add transformation ledger`
            - Enter configurations below:

                - `Source Schema`: Select source term set file from drop-down

                - `Target Schema`: Select Target term set from drop-down to be mapped to

                - `Schema Mapping File`: Upload the Schema Mapping file to be referenced for mapping in the required format(JSON)

                - `Status`: Select if the Schema Mapping is Published or Retired

            **Note: On uploading the Schema Mapping File in the required format to the transformation ledger, this triggers the process of adding the mapping for the corresponding term values.**
    
    - Term sets: Term sets support the concept of a vocabulary in the context of semantic linking
        1. Click on `Term set` > `Add term set`
            - Enter configurations below: 

                - `IRI` Term set's corresponding IRI

                - `Name` Term set title

                - `Version` Add the version number

                - `Status` Select if the Term set is Published or Retired

    - Child Term sets: Is a term set that contains a references to other term-sets (schemas)
        1. Click on `Child term sets` > `Add child term set`
        - Enter configurations below:

            - `IRI` Term set's corresponding IRI

            - `Name` Term set title

            - `Status` Select if the Term set is Published or Retired

            - `Parent term set` Select the reference to the parent term set from the drop down
    
    - Terms: A term entity can be seen as a word in our dictionary. This entity captures a unique word/term in a term-set or schema.
        1. Click on `Terms` > `Add term`
            - Enter configurations below:

                - `IRI` Term corresponding IRI

                - `Name` Term title

                - `Desciption` Term entity's description

                - `Status` Select if the Term set is Published or Retired

                - `Data Type` Term entity's corresponding data type

                - `Use` Term entity's corresponding use case

                - `Source` Term entity's corresponding source

                - `term set` Select the reference to the parent term set from the drop down

                - `Mapping` Add mappings between terms entity's of different parent term set

                - `Updated by` User that creates/updates the term

## 5. Removing Deployment
To destroy the created resources, simply run the command below in your terminal:
    
    
    docker-compose down

## API's 
 **XSS contains API endpoints which can be called from other components**
 
Query string parameter: `name` `version` `iri`

      http://localhost:8080/api/schemas/?parameter=parameter_value
    

    
**Note:This API fetches the required schema from the repository using the Name and Version or IRI parameters**

Query string parameter: `sourceName` `sourceVersion` `sourceIRI` `targetName` `targetVersion` `targetIRI`

      http://localhost:8080/api/mappings/
    
*Note: This API fetches the required mapping schema from the repository using the Source Name, Source Version, Target Name and Target Version or source IRI and Target IRI parameters*
   

## Testing

To run the automated tests on the application run the command below

Test coverage information will be stored in an htmlcov directory

```bash
docker-compose --env-file .env run app sh -c "coverage run manage.py test && coverage html && flake8"
```

## License

 This project uses the [MIT](http://www.apache.org/licenses/LICENSE-2.0) license.
  
