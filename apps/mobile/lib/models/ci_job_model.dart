class CiJobModel {
  final String id;
  final String name;
  final String status;

  CiJobModel({required this.id, required this.name, required this.status});

  factory CiJobModel.fromMap(String key, String status) {
    // ফরম্যাটিং: 'deploy_backend' -> 'Deploy Backend'
    String formattedName = key.replaceAll('_', ' ').split(' ').map((word) {
      if (word.isEmpty) return word;
      return word[0].toUpperCase() + word.substring(1);
    }).join(' ');

    return CiJobModel(
      id: key,
      name: formattedName,
      status: status,
    );
  }
}
