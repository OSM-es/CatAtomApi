from marshmallow import Schema, fields

class JobConfigSchema(Schema):
    language = fields.Str()
    parcel_parts = fields.Integer()
    parcel_dist = fields.Integer()

class JobSchema(Schema):
    linea = fields.Integer()
    building = fields.Bool()
    address = fields.Bool()
    config = fields.Nested(JobConfigSchema())
